<!DOCTYPE html>
<html lang="${locale.currentLanguageTag}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${msg("doForgotPassword")?html} - GUSTAV</title>
  <link rel="stylesheet" href="${url.resourcesPath}/css/gustav.css">
</head>
<body class="login-pf">
  <main id="kc-content" class="kc-gustav">
    <section class="kc-card">
      <h1 class="kc-title">${msg("doForgotPassword")?html}</h1>

      <#if message?has_content>
        <div class="kc-message kc-${message.type}">${message.summary?html}</div>
      </#if>

      <form id="kc-reset-password-form" action="${url.loginAction}" method="post" class="kc-form">
        <label class="kc-label" for="username">${msg("usernameOrEmail")?html}</label>
        <input class="kc-input" id="username" name="username" type="email" autocomplete="email" autofocus>
        <button class="btn btn-primary kc-submit" type="submit">${msg("doSubmit")?html}</button>
      </form>

      <div class="kc-links">
        <a href="${url.loginUrl}">${msg("doLogIn")?html}</a>
        <#if realm.registrationAllowed>
          <span> · </span>
          <a href="${url.registrationUrl}">${msg("doRegister")?html}</a>
        </#if>
      </div>
    </section>
  </main>
</body>
</html>

