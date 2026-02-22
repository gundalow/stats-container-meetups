# Project Plan: Meetup Bot Python Rewrite

This project involves rewriting the existing R-based Meetup reporting and Discourse automation system into a set of Python scripts using the new Meetup GraphQL API.

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
  "country": "US"
}
```

## 2. API Specifications

### Meetup GraphQL API
**Endpoint**: `https://api.meetup.com/gql`

**Query: Fetch Pro Groups**
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

- `config.py`: Handles loading `email.yml` and `meetups.yml`.
- `meetup_client.py`: Handles GraphQL queries and OAuth2 authentication.
- `discourse_client.py`: Handles Discourse API interactions (search, create, update).
- `cache_manager.py`: Handles JSON-based local caching.
- `report_generator.py`: Generates HTML reports and plots (using Pandas/Matplotlib/Jinja2).
- `main.py`: Orchestrates the workflow:
    1. Update group list from GitHub.
    2. Fetch groups and events from Meetup.
    3. Update Discourse topics.
    4. Generate and send email reports.

## 4. Caching Strategy
- Use `groups.json` and `events.json` in the `/srv/docker-pins/meetup` directory.
- Simple JSON serialization/deserialization for persistence.

## 5. Implementation Details

### Discourse Post Format
The `raw` content for the Discourse post will follow the specified format:
```text
[event url='{link}' start='{date}' status='public' ]
[/event]
{description}
```

### Email Reporting
- Use `Jinja2` for HTML templating.
- Use `Matplotlib` or `Plotly` to replicate the R-based plots (Activity and Trends).
- Use `smtplib` for sending emails via Gmail.

## 6. Execution Plan
1. Initialize Python environment and `requirements.txt`.
2. Implement Meetup GraphQL client.
3. Implement Discourse integration.
4. Port reporting logic and visualization.
5. Create new `Dockerfile`.
6. Final verification and removal of R scripts.
