# Classifier API

_by Tural Mahmudov <nima.bavari@gmail.com>_

Time taken: 5 hours

## Notes

Before starting, the existing code was linted and formatted, and relieved of typos.

I implemented the bonus endpoint (`GET /models/groups/`) as well, though did not add a test case for that. Please, scroll to the end of `./api/main.py` for the source.

## Scripts

Run

```sh
chmod +x ./lint.sh
./lint.sh
```

from the project directory to lint and format (in case of any change to the code).

## Use

Run `docker-compose up mysql` and `docker-compose up api` in seperate terminals in the project directory in order to broadcast the Classifier API.

While the above is running, run `docker-compose up client` to test the API endpoints.
