<!DOCTYPE html>
<html lang="${(locale.currentLanguageTag)!'de'}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <#assign page_title = msg("gustavAuthErrorTitle")>
  <title>${page_title} - GUSTAV</title>
  <link rel="stylesheet" href="${url.resourcesPath}/css/app-gustav-base.css">
  <link rel="stylesheet" href="${url.resourcesPath}/css/gustav.css">
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
    <section class="kc-card">
      <h1 class="kc-title">${page_title}</h1>

      <#if message?has_content>
        <div class="kc-message kc-${message.type}">${message.summary}</div>
      </#if>

      <p class="kc-hint">${msg("gustavAuthErrorGeneralHint")}</p>

      <#assign app_link = "">
      <#if pageRedirectUri?has_content>
        <#assign app_link = pageRedirectUri>
      <#elseif client?? && client.baseUrl?has_content>
        <#assign app_link = client.baseUrl>
      <#elseif url.loginUrl?has_content>
        <#assign app_link = url.loginUrl>
      </#if>

      <#import "_gustav_error_components.ftl" as gustav_error>
      <@gustav_error.render_recovery_links appLink=app_link />
      <@gustav_error.render_locale_links />
    </section>
  </main>
</body>
</html>
