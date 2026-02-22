import os
import json
import yaml
import requests
import argparse
import pandas as pd
import matplotlib.pyplot as plt
plt.switch_backend('Agg')
from jinja2 import Template
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

class MeetupBot:
    def __init__(self, config_path):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.meetup_config = self.config.get('meetup', {})
        self.discourse_config = self.config.get('discourse', {})
        self.email_config = self.config.get('email', {})
        self.paths = self.config.get('paths', {
            'config_dir': '/srv/docker-config/meetup',
            'pins_dir': '/srv/docker-pins/meetup'
        })

        self.access_token = None

    def get_access_token(self):
        """Refreshes the OAuth2 token."""
        url = "https://secure.meetup.com/oauth2/access"
        data = {
            'client_id': self.meetup_config.get('client_id'),
            'client_secret': self.meetup_config.get('client_secret'),
            'grant_type': 'refresh_token',
            'refresh_token': self.meetup_config.get('refresh_token'),
        }
        response = requests.post(url, data=data)
        response.raise_for_status()
        self.access_token = response.json().get('access_token')
        return self.access_token

    def graphql_query(self, query, variables=None):
        if not self.access_token:
            self.get_access_token()

        url = "https://api.meetup.com/gql"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)
        response.raise_for_status()
        return response.json()

    def fetch_network_stats(self):
        query = """
        query ($urlname: String!) {
          proNetworkByUrlname(urlname: $urlname) {
            name
            memberCount
            groups(input: { first: 200 }) {
              edges {
                node {
                  id
                  urlname
                  name
                  city
                  country
                  memberCount
                }
              }
            }
          }
        }
        """
        variables = {"urlname": self.meetup_config.get('network_urlname', 'ansible')}
        result = self.graphql_query(query, variables)
        return result.get('data', {}).get('proNetworkByUrlname', {})

    def fetch_group_events(self, urlname):
        query = """
        query ($urlname: String!) {
          groupByUrlname(urlname: $urlname) {
            unifiedEvents(input: { first: 100 }) {
              edges {
                node {
                  id
                  title
                  eventUrl
                  dateTime
                  going
                  description
                  venue {
                    name
                  }
                  status
                }
              }
            }
          }
        }
        """
        # Note: unifiedEvents returns a mix. To be safe we can use query filters
        # but the Pro API unifiedEvents usually covers recent past and future.
        variables = {"urlname": urlname}
        result = self.graphql_query(query, variables)
        events = []
        group_data = result.get('data', {}).get('groupByUrlname')
        if group_data and group_data.get('unifiedEvents'):
            for edge in group_data['unifiedEvents']['edges']:
                node = edge['node']
                events.append({
                    'id': node['id'],
                    'title': node['title'],
                    'link': node['eventUrl'],
                    'time': node['dateTime'],
                    'going': node['going'],
                    'description': node['description'],
                    'venue_name': node['venue']['name'] if node['venue'] else 'No venue',
                    'is_online_event': node['venue']['name'] == 'Online event' if node['venue'] else False,
                    'status': node['status'],
                    'urlname': urlname
                })
        return events

    def load_cache(self, filename):
        path = os.path.join(self.paths['pins_dir'], filename)
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
        return {}

    def save_cache(self, filename, data):
        os.makedirs(self.paths['pins_dir'], exist_ok=True)
        path = os.path.join(self.paths['pins_dir'], filename)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def update_data(self):
        print("Updating network stats and groups...")
        network_data = self.fetch_network_stats()
        groups = [edge['node'] for edge in network_data.get('groups', {}).get('edges', [])]

        # Caching network stats and groups
        groups_cache = {
            'network': {
                'name': network_data.get('name'),
                'memberCount': network_data.get('memberCount'),
                'updated_at': datetime.now().isoformat()
            },
            'groups': groups
        }

        # Update weekly history
        history = self.load_cache('history.json')
        if not history:
            history = []

        today = datetime.now().strftime('%Y-%m-%d')
        if not history or history[-1]['date'] != today:
            history.append({
                'date': today,
                'memberCount': network_data.get('memberCount')
            })
            self.save_cache('history.json', history)

        self.save_cache('groups.json', groups_cache)

        print(f"Fetching events for {len(groups)} groups...")
        all_events = []
        for group in groups:
            print(f"  Fetching events for {group['urlname']}...")
            try:
                events = self.fetch_group_events(group['urlname'])
                all_events.extend(events)
            except Exception as e:
                print(f"  Error fetching events for {group['urlname']}: {e}")

        # Preserve discourse_topic_url if it exists in old cache
        old_events = self.load_cache('events.json')
        if isinstance(old_events, list):
            topic_map = {e['id']: e.get('discourse_topic_url') for e in old_events if e.get('discourse_topic_url')}
            for event in all_events:
                if event['id'] in topic_map:
                    event['discourse_topic_url'] = topic_map[event['id']]

        self.save_cache('events.json', all_events)
        print("Update complete.")

    def update_discourse(self, dry_run=False):
        print("Syncing with Discourse...")
        events = self.load_cache('events.json')
        if not events:
            print("No events found in cache. Run --fetch first.")
            return

        # Filters from original script: active events in next 90 days
        now = datetime.now()
        upcoming_cutoff = now + timedelta(days=90)

        upcoming_events = [
            e for e in events
            if e['status'] == 'PUBLISHED' and now <= datetime.fromisoformat(e['time'].replace('Z', '+00:00')) <= upcoming_cutoff
        ]

        auth_headers = {
            "Api-Key": self.discourse_config.get('api_key'),
            "Api-Username": self.discourse_config.get('api_user'),
            "Content-Type": "application/json"
        }
        base_url = self.discourse_config.get('url')
        category = self.discourse_config.get('category')

        # Get existing topics
        search_str = f"#events tags:meetup status:open @{self.discourse_config.get('api_user')}"
        search_url = f"{base_url}/search.json?expanded=true&q={requests.utils.quote(search_str)}"
        resp = requests.get(search_url, headers=auth_headers)
        resp.raise_for_status()
        search_results = resp.json()

        # Map meetup_id to discourse info
        existing_map = {}
        for topic in search_results.get('topics', []):
            # We need to get the first post to get external_id
            topic_id = topic['id']
            topic_resp = requests.get(f"{base_url}/t/{topic_id}.json", headers=auth_headers)
            topic_data = topic_resp.json()
            external_id = topic_data.get('external_id')
            if external_id:
                existing_map[external_id] = {
                    'topic_id': topic_id,
                    'post_id': topic_data['post_stream']['posts'][0]['id'],
                    'title': topic['title']
                }

        for event in upcoming_events:
            title = f"{event['urlname']}: {event['title']} [{event['time'][:10]}]"
            raw = f"[event url='{event['link']}' start='{event['time'][:10]}' status='public' ]\n[/event]\n\n{event['description']}"

            if event['id'] in existing_map:
                # Update
                info = existing_map[event['id']]
                if dry_run:
                    print(f"[DRY-RUN] Would update topic {info['topic_id']}: {title}")
                else:
                    print(f"Updating topic {info['topic_id']}: {title}")
                    requests.put(f"{base_url}/t/{info['topic_id']}.json", json={"title": title, "category": category}, headers=auth_headers)
                    requests.put(f"{base_url}/posts/{info['post_id']}.json", json={"post": {"raw": raw, "edit_reason": "meetupbot api update"}}, headers=auth_headers)
                event['discourse_topic_url'] = f"{base_url}/t/{info['topic_id']}"
            else:
                # Create
                if dry_run:
                    print(f"[DRY-RUN] Would create topic: {title}")
                else:
                    print(f"Creating topic: {title}")
                    post_data = {
                        "title": title,
                        "raw": raw,
                        "category": category,
                        "external_id": event['id'],
                        "tags": ["meetup"]
                    }
                    resp = requests.post(f"{base_url}/posts.json", json=post_data, headers=auth_headers)
                    if resp.status_code == 200:
                        topic_id = resp.json().get('topic_id')
                        event['discourse_topic_url'] = f"{base_url}/t/{topic_id}"
                    else:
                        print(f"Failed to create topic: {resp.text}")

        if not dry_run:
            self.save_cache('events.json', events)
        print("Discourse sync complete.")

    def generate_report(self):
        print("Generating report...")
        groups_cache = self.load_cache('groups.json')
        events_cache = self.load_cache('events.json')
        history_cache = self.load_cache('history.json')

        if not groups_cache or not events_cache:
            print("Missing data for report. Run --fetch first.")
            return

        network_stats = groups_cache['network']
        groups_df = pd.DataFrame(groups_cache['groups'])
        events_df = pd.DataFrame(events_cache)
        history_df = pd.DataFrame(history_cache)

        # 1. Network Trend Graph
        plt.figure(figsize=(10, 5))
        if not history_df.empty:
            history_df['date'] = pd.to_datetime(history_df['date'])
            plt.plot(history_df['date'], history_df['memberCount'], marker='o')
            plt.title('Meetup Pro Network Member Growth')
            plt.xlabel('Date')
            plt.ylabel('Members')
            plt.grid(True)
        graph_path = os.path.join(self.paths['pins_dir'], 'network_trend.png')
        plt.savefig(graph_path)
        plt.close()

        # 2. Activity Trends (RSVPs)
        # We need to calculate trends for 7, 30, 60, 90 days
        now = datetime.now()
        events_df['time'] = pd.to_datetime(events_df['time'].str.replace('Z', '+00:00'))

        def get_rsvp_sum(days):
            cutoff = now - timedelta(days=days)
            relevant = events_df[(events_df['time'] >= cutoff) & (events_df['time'] <= now)]
            return relevant.groupby('urlname')['going'].sum().reset_index()

        trends = {
            '7d': get_rsvp_sum(7),
            '30d': get_rsvp_sum(30),
            '60d': get_rsvp_sum(60),
            '90d': get_rsvp_sum(90)
        }

        activity_table = groups_df[['urlname', 'name', 'memberCount']].copy()
        for label, df in trends.items():
            activity_table = activity_table.merge(df, on='urlname', how='left').fillna(0)
            activity_table = activity_table.rename(columns={'going': f'RSVPs_{label}'})

        # 3. HTML Generation
        html_template = """
        <html>
        <body>
            <h1>Meetup Pro Report: {{ network.name }}</h1>
            <p>Total Members: {{ network.memberCount }}</p>
            <p>Report Date: {{ today }}</p>

            <h2>Network Growth</h2>
            <img src="cid:network_trend">

            <h2>Group Activity</h2>
            <table border="1">
                <tr>
                    <th>Group Name</th>
                    <th>Members</th>
                    <th>RSVPs (7d)</th>
                    <th>RSVPs (30d)</th>
                    <th>RSVPs (60d)</th>
                    <th>RSVPs (90d)</th>
                </tr>
                {% for _, row in activity.iterrows() %}
                <tr>
                    <td>{{ row['name'] }}</td>
                    <td>{{ row['memberCount'] }}</td>
                    <td>{{ row['RSVPs_7d'] | int }}</td>
                    <td>{{ row['RSVPs_30d'] | int }}</td>
                    <td>{{ row['RSVPs_60d'] | int }}</td>
                    <td>{{ row['RSVPs_90d'] | int }}</td>
                </tr>
                {% endfor %}
            </table>

            <h2>Upcoming Events (Next 90 Days)</h2>
            <table border="1">
                <tr>
                    <th>Date</th>
                    <th>Event</th>
                    <th>Group</th>
                    <th>Going</th>
                    <th>Virtual?</th>
                    <th>Link</th>
                </tr>
                {% for _, row in upcoming.iterrows() %}
                <tr>
                    <td>{{ row['time'].strftime('%Y-%m-%d') }}</td>
                    <td>{{ row['title'] }}</td>
                    <td>{{ row['urlname'] }}</td>
                    <td>{{ row['going'] }}</td>
                    <td>{{ 'Yes' if row['is_online_event'] else 'No' }}</td>
                    <td><a href="{{ row['discourse_topic_url'] or row['link'] }}">Link</a></td>
                </tr>
                {% endfor %}
            </table>
        </body>
        </html>
        """

        upcoming_events = events_df[(events_df['time'] >= now) & (events_df['time'] <= now + timedelta(days=90))].sort_values('time')

        template = Template(html_template)
        html_content = template.render(
            network=network_stats,
            today=now.strftime('%Y-%m-%d'),
            activity=activity_table.sort_values('RSVPs_30d', ascending=False).head(20),
            upcoming=upcoming_events
        )

        self.send_email(html_content, graph_path)

    def send_email(self, html_content, graph_path):
        print("Sending email...")
        msg = MIMEMultipart('related')
        msg['Subject'] = f"Meetup Pro Report - {datetime.now().strftime('%Y-%m-%d')}"
        msg['From'] = self.email_config.get('username')
        msg['To'] = ", ".join(self.email_config.get('targets', []))

        msg_alternative = MIMEMultipart('alternative')
        msg.attach(msg_alternative)
        msg_alternative.attach(MIMEText(html_content, 'html'))

        with open(graph_path, 'rb') as f:
            img = MIMEImage(f.read())
            img.add_header('Content-ID', '<network_trend>')
            msg.attach(img)

        try:
            with smtplib.SMTP(self.email_config.get('smtp_server'), self.email_config.get('smtp_port')) as server:
                server.starttls()
                server.login(self.email_config.get('username'), self.email_config.get('password'))
                server.send_message(msg)
            print("Email sent successfully.")
        except Exception as e:
            print(f"Failed to send email: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Meetup Bot Python Rewrite")
    parser.add_argument("--config", default="credentials.yml", help="Path to credentials.yml")
    parser.add_argument("--fetch", action="store_true", help="Fetch data from Meetup API")
    parser.add_argument("--discourse", action="store_true", help="Sync events to Discourse")
    parser.add_argument("--report", action="store_true", help="Generate and send email report")
    parser.add_argument("--dry-run", action="store_true", help="Dry run for Discourse updates")
    args = parser.parse_args()

    bot = MeetupBot(args.config)

    if args.fetch:
        bot.update_data()

    if args.discourse:
        bot.update_discourse(dry_run=args.dry_run)

    if args.report:
        bot.generate_report()

    if not (args.fetch or args.discourse or args.report):
        parser.print_help()
