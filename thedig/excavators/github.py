import requests

GITHUB_GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
GITHUB_GRAPHQL_USERS = """{
  users_by_name: search(type: USER, query: "${name}", first: 10) {
    users: edges {
      user: node {
        ... on User {
          login
          name
          email
          avatarUrl
          url
          websiteUrl
          location
          company
          bio
          twitterUsername
        }
      }
    }
    pageInfo {
      hasNextPage
    }
  }
}"""


def github_query(query: str,
                 params: dict,
                 token: str,
                 endpoint=GITHUB_GRAPHQL_ENDPOINT):
    r = requests.post(endpoint,
                      headers={'Authorization': "bearer %s " % token},
                      data=query.format(**params))
    r.raise_for_status()
    return r.json()


def users_by_name(results: dict, name: str) -> list[dict]:
    data = results["data"]["location_users"]
    users = [u['user'] for u in data["users"] if u['user']]
    return users
