<!DOCTYPE html>
<html lang="${(locale.currentLanguageTag)!'de'}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${msg("updatePasswordTitle")!msg("doResetPassword")} - GUSTAV</title>
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
  <main id="kc-content" class="kc-gustav kc-auth-shell">
    <section class="kc-card kc-auth-card">
      <div class="kc-form-shell">
        <h1 class="kc-title">${msg("updatePasswordTitle")!msg("doResetPassword")}</h1>

        <#if message?has_content>
          <div class="kc-message kc-${message.type}">${message.summary}</div>
        </#if>

        <form id="kc-passwd-update-form" action="${url.loginAction}" method="post" class="kc-form">
          <label class="kc-field workspace-field" for="password-new">
            <span class="kc-label">${msg("password")}</span>
            <input class="kc-input" id="password-new" name="password-new" type="password" autocomplete="new-password" autofocus>
          </label>

          <label class="kc-field workspace-field" for="password-confirm">
            <span class="kc-label">${msg("passwordConfirm")}</span>
            <input class="kc-input" id="password-confirm" name="password-confirm" type="password" autocomplete="new-password">
          </label>

          <button class="btn btn-primary kc-submit workspace-button" type="submit">${msg("doSubmit")}</button>
        </form>

        <div class="kc-links">
          <a href="${url.loginUrl}">${msg("doLogIn")}</a>
        </div>
      </div>
    </section>
  </main>
</body>
</html>
