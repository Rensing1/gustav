<!DOCTYPE html>
<html lang="${(locale.currentLanguageTag)!'de'}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${msg("doForgotPassword")} - GUSTAV</title>
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
      <h1 class="kc-title">${msg("doForgotPassword")}</h1>

      <#if message?has_content>
        <div class="kc-message kc-${message.type}">${message.summary}</div>
      </#if>

      <form id="kc-reset-password-form" action="${url.loginAction}" method="post" class="kc-form">
        <label class="kc-label" for="username">${msg("usernameOrEmail")}</label>
        <input class="kc-input" id="username" name="username" type="email" autocomplete="email" autofocus>
        <button class="btn btn-primary kc-submit" type="submit">${msg("doSubmit")}</button>
      </form>

      <div class="kc-links">
        <a href="${url.loginUrl}">${msg("doLogIn")}</a>
        <#if realm.registrationAllowed>
          <span> · </span>
          <a href="${url.registrationUrl}">${msg("doRegister")}</a>
        </#if>
      </div>
    </section>
  </main>
</body>
</html>
