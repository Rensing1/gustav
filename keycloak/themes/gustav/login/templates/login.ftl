<!DOCTYPE html>
<html lang="${locale.currentLanguageTag}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${msg("doLogIn")?html} - GUSTAV</title>
  <link rel="stylesheet" href="${url.resourcesPath}/css/gustav.css">
</head>
<body class="login-pf">
  <main id="kc-content" class="kc-gustav">
    <section class="kc-card">
      <h1 class="kc-title">${msg("doLogIn")?html}</h1>

      <#if message?has_content>
        <div class="kc-message kc-${message.type}">${message.summary?html}</div>
      </#if>

      <form id="kc-form-login" action="${url.loginAction}" method="post" class="kc-form">
        <label class="kc-label" for="username">${msg("usernameOrEmail")?html}</label>
        <input class="kc-input" id="username" name="username" type="text" autofocus autocomplete="username">

        <label class="kc-label" for="password">${msg("password")?html}</label>
        <input class="kc-input" id="password" name="password" type="password" autocomplete="current-password">

        <button class="btn btn-primary kc-submit" type="submit">${msg("doLogIn")?html}</button>
      </form>

      <div class="kc-links">
        <#if realm.resetPasswordAllowed>
          <a href="${url.loginResetCredentialsUrl}">${msg("doForgotPassword")?html}</a>
        </#if>
        <#if realm.registrationAllowed>
          <span> · </span>
          <a href="${url.registrationUrl}">${msg("doRegister")?html}</a>
        </#if>
      </div>
    </section>
  </main>
</body>
</html>

