import hmac
from flask import Flask, request, Response

# An example of how to verify the HMAC signature
# of the received Sarif log body.

app = Flask("Example")

@app.route("/sarif", methods=['POST'])
async def validate__hmac_signature():
    shared_secret = "MySharedSecret-12344$abc!123"
    sig = request.headers['x-cx-signature']
    alg = request.headers['x-cx-signature-alg']
    print(f"Received message with signature: {sig} generated using algorithm {alg}")

    h = hmac.new(bytes(shared_secret, 'UTF-8'), request.data, alg)
    if h.hexdigest() != sig:
        print(f"Calculated signature {h.hexdigest()} is invalid.")
        return Response(status=403)
    else:
      print("The signature verified correctly.")
      return Response(status=204)
