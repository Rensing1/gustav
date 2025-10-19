<!DOCTYPE html>
<html lang="${(locale.currentLanguageTag)!'de'}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${msg("doLogIn")} - GUSTAV</title>
  <!-- Base app CSS (shared) + small login overrides -->
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
      <h1 class="kc-title">${msg("doLogIn")}</h1>

      <#if message?has_content>
        <div class="kc-message kc-${message.type}">${message.summary}</div>
      </#if>

      <form id="kc-form-login" action="${url.loginAction}" method="post" class="kc-form">
        <label class="kc-label" for="username">${msg("usernameOrEmail")}</label>
        <input class="kc-input" id="username" name="username" type="email" autofocus autocomplete="email">

        <label class="kc-label" for="password">${msg("password")}</label>
        <input class="kc-input" id="password" name="password" type="password" autocomplete="current-password">

        <button class="btn btn-primary kc-submit" type="submit">${msg("doLogIn")}</button>
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
    </section>
  </main>
</body>
</html>
