// A path whose last segment has no extension is one of the app's routes.
function handler(event) {
  var request = event.request;
  var uri = request.uri;
  if (uri.slice(uri.lastIndexOf("/") + 1).indexOf(".") === -1) {
    request.uri = "/index.html";
  }
  return request;
}
