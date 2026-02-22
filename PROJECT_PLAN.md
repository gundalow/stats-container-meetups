# Project Plan: Meetup Bot Python Rewrite

This project involves rewriting the existing R-based Meetup reporting and Discourse automation system into a single Python script using the new Meetup GraphQL API.

## 1. Data Structures

### Group Data (Cached in `groups.json`)
```json
{
  "urlname": "Ansible-Minneapolis",
  "id": "123456",
  "name": "Minneapolis Ansible User Group",
  "country": "US",
  "city": "Minneapolis"
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
  "duration": "PT2H",
  "going": 25,
  "description": "...",
  "venue_name": "Online event",
  "is_online_event": true,
  "country": "US",
  "discourse_topic_url": "https://forum.ansible.com/t/12345"
}
```

## 2. API Specifications

### Meetup GraphQL API
**Endpoint**: `https://api.meetup.com/gql`

**Query: Fetch Pro Groups** (Directly from the Pro Network, removing need for `meetups.yml`)
```graphql
query ($urlname: String!) {
  proNetworkByUrlname(urlname: $urlname) {
    groups(input: { first: 200 }) {
      edges {
        node {
          id
          urlname
          name
          city
          country
        }
      }
    }
  }
}
```

**Query: Fetch Group Events**
```graphql
query ($urlname: String!) {
  groupByUrlname(urlname: $urlname) {
    upcomingEvents(input: { first: 20 }) {
      edges {
        node {
          id
          title
          eventUrl
          dateTime
          duration
          going
          description
          venue {
            name
          }
        }
      }
    }
    pastEvents(input: { first: 20 }) {
      edges {
        node {
          id
          title
          eventUrl
          dateTime
          duration
          going
          description
          venue {
            name
          }
        }
      }
    }
  }
}
```

### Discourse API
- **Search**: `GET /search.json?q=#events tags:meetup status:open @MeetupBot`
- **Get Topic**: `GET /t/{topic_id}.json`
- **Create Post/Topic**: `POST /posts`
- **Update Topic**: `PUT /t/{topic_id}.json`
- **Update Post**: `PUT /posts/{post_id}.json`

## 3. Python Script Architecture

A single script `meetup_bot.py` will handle all operations to simplify maintenance.

- **CLI Interface**: Uses `argparse` to support:
    - `--dry-run`: Prints Discourse changes without applying them.
    - `--fetch`: Fetches data from Meetup.
    - `--discourse`: Updates the forum.
    - `--email`: Sends the report.
- **Config Loader**: Loads `email.yml` for credentials and settings.
- **Meetup Client**: Handles GraphQL queries and OAuth2.
- **Discourse Client**: Handles forum interactions.
- **Cache Manager**: Handles JSON-based local caching (`groups.json`, `events.json`).
- **Report Generator**: Replicates R Markdown logic using Jinja2 and Matplotlib.

## 4. Code Snippets

### Meetup GraphQL Client (Python)
```python
import requests

def fetch_meetup_data(query, variables, token):
    url = "https://api.meetup.com/gql"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)
    return response.json()
```

### Discourse Update with Dry-Run support
```python
def update_discourse_topic(url, auth, topic_id, title, category, dry_run=False):
    if dry_run:
        print(f"[DRY-RUN] Would update topic {topic_id} with title: {title}")
        return

    # Actual API call...
    requests.put(f"{url}/t/{topic_id}.json", json={"title": title, "category": category}, headers=auth)
```

## 5. Caching Strategy
- Use `groups.json` and `events.json` in the `/srv/docker-pins/meetup` directory.
- `events.json` will store `discourse_topic_url` to link Meetup events to forum posts.

## 6. Implementation Details

### Discourse Post Format
Matches the required BBCode format:
```text
[event url='{link}' start='{date}' status='public' ]
[/event]
{description}
```

### Simplified Data Transformation
- Directly request required fields via GraphQL to minimize post-processing.
- Use `pandas` for any remaining trend analysis and report generation.

## 7. Execution Plan
1. Initialize Python environment and `requirements.txt`.
2. Implement `meetup_bot.py` with GraphQL and Discourse logic.
3. Add `--dry-run` functionality.
4. Port reporting logic and visualization to Python.
5. Create new `Dockerfile`.
6. Final verification and removal of R scripts.
