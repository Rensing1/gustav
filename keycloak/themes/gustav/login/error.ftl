<!DOCTYPE html>
<html lang="${(locale.currentLanguageTag)!'de'}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <#assign page_title = msg("gustavAuthErrorTitle")>
  <title>${page_title} - GUSTAV</title>
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
      <h1 class="kc-title">${page_title}</h1>

      <#if message?has_content>
        <div class="kc-message kc-${message.type}">${message.summary}</div>
      </#if>

      <p class="kc-hint">${msg("gustavAuthErrorGeneralHint")}</p>

      <#import "_gustav_error_components.ftl" as gustav_error>
      <#assign client_base_url = "">
      <#if client?? && client.baseUrl?has_content>
        <#assign client_base_url = client.baseUrl>
      </#if>
      <#assign app_link = gustav_error.resolve_primary_app_link(
        pageRedirectUri=(pageRedirectUri!""),
        clientBaseUrl=client_base_url
      )>

      <@gustav_error.render_recovery_links appLink=app_link />
      <@gustav_error.render_locale_links />
      </div>
    </section>
    </div>
  </main>
</body>
</html>
