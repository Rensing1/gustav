<!DOCTYPE html>
<html lang="${(locale.currentLanguageTag)!'de'}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${msg("doRegister")} - GUSTAV</title>
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
      <h1 class="kc-title">${msg("doRegister")}</h1>

      <#if message?has_content>
        <div class="kc-message kc-${message.type}">${message.summary}</div>
      </#if>

      <form id="kc-register-form" action="${url.registrationAction}" method="post" class="kc-form">
        <label class="kc-label" for="firstName">${msg("firstName")}</label>
        <input class="kc-input" id="firstName" name="firstName" type="text" autocomplete="given-name">

        <label class="kc-label" for="lastName">${msg("lastName")}</label>
        <input class="kc-input" id="lastName" name="lastName" type="text" autocomplete="family-name">

        <#if !realm.registrationEmailAsUsername>
          <label class="kc-label" for="username">${msg("username")}</label>
          <input class="kc-input" id="username" name="username" type="text" autocomplete="username">
        </#if>

        <label class="kc-label" for="email">${msg("email")}</label>
        <input class="kc-input" id="email" name="email" type="email" autocomplete="email">

        <label class="kc-label" for="password">${msg("password")}</label>
        <input class="kc-input" id="password" name="password" type="password" autocomplete="new-password">

        <label class="kc-label" for="password-confirm">${msg("passwordConfirm")}</label>
        <input class="kc-input" id="password-confirm" name="password-confirm" type="password" autocomplete="new-password">

        <button class="btn btn-primary kc-submit" type="submit">${msg("doRegister")}</button>
      </form>

      <div class="kc-links">
        <a href="${url.loginUrl}">${msg("doLogIn")}</a>
      </div>
    </section>
  </main>
</body>
</html>
