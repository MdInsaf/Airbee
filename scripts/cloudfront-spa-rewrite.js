async function handler(event) {
  var request = event.request;
  var uri = request.uri || "/";

  if (uri.startsWith("/api/") || uri.startsWith("/ai/") || uri.startsWith("/public/")) {
    return request;
  }

  if (uri === "/" || uri.endsWith("/") || !uri.includes(".")) {
    request.uri = "/index.html";
  }

  return request;
}