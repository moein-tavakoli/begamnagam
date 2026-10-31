/* No external validator or persisted credentials; all assets are staff-only. */
window.addEventListener("DOMContentLoaded", function () {
  window.ui = SwaggerUIBundle({
    url: "/api/v2/document/openapi.json",
    dom_id: "#swagger-ui",
    deepLinking: true,
    filter: true,
    displayRequestDuration: true,
    persistAuthorization: false,
    validatorUrl: null,
    defaultModelsExpandDepth: -1,
    requestInterceptor: function (request) {
      request.credentials = "same-origin";
      var cookie = document.cookie.split("; ").find(function (part) { return part.startsWith("csrftoken="); });
      if (cookie) request.headers["X-CSRFToken"] = decodeURIComponent(cookie.substring("csrftoken=".length));
      return request;
    }
  });
});
