# Project Plan: Meetup Bot Python Rewrite (v3)

This project involves rewriting the existing R-based Meetup reporting and Discourse automation system into a single Python script (`meetup_bot.py`) using the new Meetup Pro GraphQL API.

## 1. Data Structures

### Group & Network Data (Cached in `groups.json`)
```json
{
  "network": {
    "urlname": "ansible",
    "memberCount": 50000,
    "stats_history": [
      {"date": "2024-01-01", "memberCount": 49500},
      {"date": "2024-01-08", "memberCount": 49650}
    ]
  },
  "groups": [
    {
      "urlname": "Ansible-Minneapolis",
      "id": "123456",
      "name": "Minneapolis Ansible User Group",
      "country": "US",
      "city": "Minneapolis",
      "memberCount": 1200
    }
  ]
}
```

### Event Data (Cached in `events.json`)
```json
{
  "id": "311874047",
  "urlname": "Ansible-Minneapolis",
  "title": "Ansible on Localhost",
  "link": "https://www.meetup.com/ansible-minneapolis/events/311874047/",
  "status": "upcoming",
  "time": "2025-12-19T18:00:00Z",
  "going": 25,
  "description": "...",
  "venue_name": "Online event",
  "is_online_event": true,
  "discourse_topic_url": "https://forum.ansible.com/t/12345"
}
```

## 2. API Specifications

### Meetup GraphQL API
**Endpoint**: `https://api.meetup.com/gql`

**Query: Fetch Pro Network Stats & Groups**
```graphql
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
```

**Query: Fetch Group Events**
(Using the new GraphQL style to get exactly what we need)
```graphql
query ($urlname: String!) {
  groupByUrlname(urlname: $urlname) {
    unifiedEvents(input: { first: 50 }) {
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
```

### Discourse API
- **Search**: `GET /search.json?q=#events tags:meetup status:open @MeetupBot`
- **Update Topic/Post**: `PUT /t/{topic_id}.json` and `PUT /posts/{post_id}.json`

## 3. Python Script Architecture (`meetup_bot.py`)

- **Configuration**: Single `credentials.yml` for Meetup OAuth, Discourse API, and SMTP.
- **CLI Options**:
    - `--dry-run`: Prints Discourse changes without applying them.
    - `--fetch`: Updates local cache from Meetup API.
    - `--discourse`: Syncs events to Discourse.
    - `--report`: Generates and sends email reports.
- **Caching**: Local JSON files in `/srv/docker-pins/meetup`.
    - Weekly snapshots for Network member trends.

## 4. Reporting & Visualization

### Multiple Report Types:
1. **Executive Summary**: Total Network growth and high-level activity.
2. **Activity Table**: Groups with current RSVPs and trends (Weekly, 30, 60, 90 days).
3. **Upcoming Events**: Categorized list of future meetups.

### Visualization:
- **Matplotlib/Seaborn**: Generate trend graphs for Network membership and event attendance.
- **HTML/Jinja2**: Clean HTML tables with conditional formatting for trends.

## 5. Implementation Details

### Discourse Post Format
```text
[event url='{link}' start='{date}' status='public' ]
[/event]
{description}
```

### Credentials (`credentials.yml`)
```yaml
meetup:
  client_id: "..."
  client_secret: "..."
  refresh_token: "..."
discourse:
  url: "https://forum.ansible.com"
  api_key: "..."
  api_user: "MeetupBot"
  category: 1
email:
  smtp_server: "smtp.gmail.com"
  username: "..."
  password: "..."
  targets: ["..."]
```

## 6. Execution Plan
1. Initialize Python environment and `requirements.txt`.
2. Implement `meetup_bot.py` with GraphQL, Discourse, and Caching logic.
3. Replicate trend analysis (Weekly, 30/60/90 day windows) using cached data.
4. Implement reporting engine (HTML Tables + Graphs).
5. Create new `Dockerfile`.
6. Cleanup R scripts and legacy config files.
