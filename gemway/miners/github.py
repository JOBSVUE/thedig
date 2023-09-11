import requests

GITHUB_TOKEN = "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"
GITHUB_GRAPHQL_ENDPOINT = "https://api.github.com/graphql" 
GITHUB_GRAPHQL_USERS = """{
  users_by_name: search(type: USER, query: "${name}", first: 3) {
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


async def github_query(query: str, params: dict, token=GITHUB_TOKEN, endpoint=GITHUB_GRAPHQL_ENDPOINT):
    r = requests.post(endpoint,
                      headers={'Authorization': "bearer %s " % token},
                      data=query.format(**params))
    if not r.ok:
        r.raise_for_status()
    return r.json()

async def users_by_name(name: str) -> list[dict]:
    data_json = 
    try:
        data = data_json.json()["data"]["location_users"]
    except TypeError:
        raise TypeError("GraphQL query: %s\nAnswer: %s" % (self._graphql_query("users", created_date, cursor), data_json.text))
    self.users.extend([u['user'] for u in data["users"] if u['user']])
    hasNextPage = data["pageInfo"]["hasNextPage"]
    cursor = ', after: \\"%s\\"' % data["pageInfo"]["endCursor"]
