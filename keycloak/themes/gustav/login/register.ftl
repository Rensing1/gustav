<!DOCTYPE html>
<html lang="${(locale.currentLanguageTag)!'de'}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${msg("doRegister")} - GUSTAV</title>
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
        <h1 class="kc-title">${msg("doRegister")}</h1>

        <#if message?has_content>
          <div class="kc-message kc-${message.type}">${message.summary}</div>
        </#if>

        <form id="kc-register-form" action="${url.registrationAction}" method="post" class="kc-form">
          <label class="kc-field workspace-field" for="display_name">
            <span class="kc-label">${msg("gustavDisplayName", "Wie möchtest du genannt werden?")}</span>
            <input class="kc-input" id="display_name" name="user.attributes.display_name" type="text" autocomplete="nickname" required>
          </label>
          <!-- Simplified registration: use a single display name instead of separate first/last name fields -->

          <!-- Email is used as username; no separate username field -->

          <label class="kc-field workspace-field" for="email">
            <span class="kc-label">${msg("email")}</span>
            <input class="kc-input" id="email" name="email" type="email" autocomplete="email">
          </label>

          <label class="kc-field workspace-field" for="password">
            <span class="kc-label">${msg("password")}</span>
            <input class="kc-input" id="password" name="password" type="password" autocomplete="new-password">
          </label>

          <label class="kc-field workspace-field" for="password-confirm">
            <span class="kc-label">${msg("passwordConfirm")}</span>
            <input class="kc-input" id="password-confirm" name="password-confirm" type="password" autocomplete="new-password">
          </label>

          <button class="btn btn-primary kc-submit workspace-button" type="submit">${msg("doRegister")}</button>
        </form>

        <div class="kc-links">
          <a href="${url.loginUrl}">${msg("doLogIn")}</a>
        </div>
      </div>
    </section>
  </main>
</body>
</html>
