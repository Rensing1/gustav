<!DOCTYPE html>
<html lang="${(locale.currentLanguageTag)!'de'}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${msg("emailVerifyTitle")} - GUSTAV</title>
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
      <h1 class="kc-title">${msg("emailVerifyTitle")}</h1>

      <#if message?has_content>
        <div class="kc-message kc-${message.type}">${message.summary}</div>
      </#if>

      <#if user?? && user.email?has_content>
        <p class="kc-hint">${msg("emailVerifyInstruction1", user.email)}</p>
      <#else>
        <p class="kc-hint">${msg("emailVerifyInstruction2")}</p>
      </#if>

      <div class="kc-links">
        <#if url.loginAction?has_content>
          <a href="${url.loginAction}">${msg("doClickHere")}</a>
          <span> · </span>
        </#if>
        <#if url.loginUrl?has_content>
          <a href="${url.loginUrl}">${msg("doLogIn")}</a>
        </#if>
      </div>
      </div>
    </section>
    </div>
  </main>
</body>
</html>
