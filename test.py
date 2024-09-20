import jwt, time, requests

# Add: PyJWT, cryptography



pem = "./secrets/ghe-app-priv-key"
app_id = 5


with open(pem, "rb") as f:
    signing_key = f.read()

payload = {
    'iat' : int(time.time()),
    "exp" : int(time.time()) + 600,
    'iss' : app_id,
    'alg' : "RS256"
}

encoded_jwt = jwt.encode(payload, signing_key, algorithm='RS256')

print(f"JWT:  {encoded_jwt}")

resp = requests.post(f"http://ghe.pot8o.site/api/v3/app/installations/26/access_tokens", headers = { 
    'Accept' : 'application/vnd.github+json',
    'Authorization' : f"Bearer {encoded_jwt}",
    'X-GitHub-Api-Version' : '2022-11-28'
    })

# resp = requests.get(f"http://ghe.pot8o.site/api/v3/app/installations", headers = { 
#     'Accept' : 'application/vnd.github+json',
#     'Authorization' : f"Bearer {encoded_jwt}",
#     'X-GitHub-Api-Version' : '2022-11-28'})

print(resp.status_code)
print(resp.url)
print(resp.headers)
print(resp.text)
