async function handler(event) {
  var request = event.request;
  var hostHeader = request.headers.host;

  if (hostHeader && hostHeader.value) {
    request.headers["x-forwarded-host"] = {
      value: hostHeader.value,
    };
  }

  return request;
}