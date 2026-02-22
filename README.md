## Docker Container for Meetup Reports (Python Rewrite)

This container handles the gathering of Ansible Meetup data via the Meetup Pro GraphQL API, generating and sending email reports, and updating Discourse topics.

## Setup

This container requires two mount points:
- a config dir mounted to `/srv/docker-config/meetup` for `credentials.yml`
- a `pins` dir mounted to `/srv/docker-pins/meetup` for storing/reading JSON data

### Example dir layout

Inside the container it should look like this:
```
/srv/docker-config
└── meetup
    └── credentials.yml
/srv/docker-pins
└── meetup
```

### Credentials file

Copy `credentials.yml.example` to `credentials.yml` and fill in your details (Meetup OAuth, Discourse API, Email SMTP).

## Build the container

```
podman build --tag meetupbot-py .
```

## Run the container

### Fetch data from Meetup

```
podman run --rm -v /path/to/config:/srv/docker-config/meetup -v /path/to/pins:/srv/docker-pins/meetup meetupbot-py --config /srv/docker-config/meetup/credentials.yml --fetch
```

### Sync to Discourse (with Dry Run)

```
podman run --rm -v /path/to/config:/srv/docker-config/meetup -v /path/to/pins:/srv/docker-pins/meetup meetupbot-py --config /srv/docker-config/meetup/credentials.yml --discourse --dry-run
```

### Generate and Send Report

```
podman run --rm -v /path/to/config:/srv/docker-config/meetup -v /path/to/pins:/srv/docker-pins/meetup meetupbot-py --config /srv/docker-config/meetup/credentials.yml --report
```
