<!DOCTYPE html>
<html lang="${(locale.currentLanguageTag)!'de'}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${msg("gustavLogoutConfirmTitle")} - GUSTAV</title>
  <link rel="stylesheet" href="${url.resourcesPath}/css/auth-theme.css?v=${properties.gustavThemeVersion!"dev"}">
  <link rel="stylesheet" href="${url.resourcesPath}/css/gustav.css?v=${properties.gustavThemeVersion!"dev"}">
  <script>
    (function(){
      try {
        var saved = localStorage.getItem('gustav-theme');
        if (saved === 'everforest-dark-hard' || saved === 'rose-pine-dawn') {
          document.documentElement.setAttribute('data-theme', saved);
        }
      } catch (e) { /* ignore */ }
    })();
  </script>
</head>
<body class="login-pf">
  <main id="kc-content" class="kc-gustav">
    <div class="kc-auth-shell">
      <section class="kc-card">
        <div class="kc-auth-card">
      <div class="kc-form-shell">
        <h1 class="kc-title">${msg("gustavLogoutConfirmTitle")}</h1>
        <p class="kc-hint">${msg("gustavLogoutConfirmHint")}</p>

        <#if message?has_content>
          <div class="kc-message kc-${message.type}">${message.summary}</div>
        </#if>

        <form id="kc-logout-confirm" class="kc-form" action="${url.logoutConfirmAction}" method="post">
          <button class="btn btn-primary kc-submit workspace-button" type="submit">
            ${msg("gustavLogoutConfirmSubmit")}
          </button>
        </form>

        <#import "_gustav_error_components.ftl" as gustav_error>
        <#assign client_base_url = "">
        <#if client?? && client.baseUrl?has_content>
          <#assign client_base_url = client.baseUrl>
        </#if>
        <#assign app_link = gustav_error.resolve_primary_app_link(
          pageRedirectUri=(pageRedirectUri!""),
          clientBaseUrl=client_base_url
        )>
        <#if app_link?has_content>
          <div class="kc-links">
            <a href="${app_link}">${msg("gustavBackToApp")}</a>
          </div>
        </#if>
        <@gustav_error.render_locale_links />
        </div>
      </section>
    </div>
  </main>
</body>
</html>
