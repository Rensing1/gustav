<!DOCTYPE html>
<html lang="${(locale.currentLanguageTag)!'de'}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${msg("doLogIn")} - GUSTAV</title>
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
        <h1 class="kc-title">${msg("doLogIn")}</h1>

        <#if message?has_content>
          <div class="kc-message kc-${message.type}">${message.summary}</div>
        </#if>

        <form id="kc-form-login" action="${url.loginAction}" method="post" class="kc-form">
          <label class="kc-field workspace-field" for="username">
            <span class="kc-label">${msg("usernameOrEmail")}</span>
            <input class="kc-input" id="username" name="username" type="email" autofocus autocomplete="email">
          </label>

          <label class="kc-field workspace-field" for="password">
            <span class="kc-label">${msg("password")}</span>
            <input class="kc-input" id="password" name="password" type="password" autocomplete="current-password">
          </label>

          <#if realm.rememberMe>
            <div class="kc-remember-me">
              <input id="rememberMe" name="rememberMe" type="checkbox">
              <label for="rememberMe">${msg("rememberMe")}</label>
            </div>
          </#if>

          <button class="btn btn-primary kc-submit workspace-button" type="submit">${msg("doLogIn")}</button>
        </form>

        <div class="kc-links">
          <#if realm.resetPasswordAllowed>
            <a href="${url.loginResetCredentialsUrl}">${msg("doForgotPassword")}</a>
          </#if>
          <#if realm.registrationAllowed>
            <span> · </span>
            <a href="${url.registrationUrl}">${msg("doRegister")}</a>
          </#if>
        </div>
      </div>
    </section>
  </main>
</body>
</html>
