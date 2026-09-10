<#-- One frame for all auth flows; session checks remain enabled for inherited Keycloak forms. -->
<#macro document title sessionChecks=false>
<!DOCTYPE html>
<html lang="${(locale.currentLanguageTag)!'de'}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${title} - GUSTAV</title>
  <script src="${url.resourcesPath}/js/theme.js?v=${properties.gustavThemeVersion!"dev"}"></script>
  <link rel="stylesheet" href="${url.resourcesPath}/fonts/inter/latin-400.css">
  <link rel="stylesheet" href="${url.resourcesPath}/fonts/inter/latin-700.css">
  <link rel="stylesheet" href="${url.resourcesPath}/fonts/space-grotesk/latin-400.css">
  <link rel="stylesheet" href="${url.resourcesPath}/fonts/space-grotesk/latin-700.css">
  <link rel="stylesheet" href="${url.resourcesPath}/css/theme-tokens.css?v=${properties.gustavThemeVersion!"dev"}">
  <link rel="stylesheet" href="${url.resourcesPath}/css/auth-theme.css?v=${properties.gustavThemeVersion!"dev"}">
  <link rel="stylesheet" href="${url.resourcesPath}/css/gustav.css?v=${properties.gustavThemeVersion!"dev"}">
  <#if sessionChecks>
    <#if properties.scripts?has_content>
      <#list properties.scripts?split(' ') as script>
        <script src="${url.resourcesPath}/${script}" type="text/javascript"></script>
      </#list>
    </#if>
    <#if scripts??>
      <#list scripts as script>
        <script src="${script}" type="text/javascript"></script>
      </#list>
    </#if>
    <script type="importmap">
      { "imports": { "rfc4648": "${url.resourcesCommonPath}/vendor/rfc4648/rfc4648.js" } }
    </script>
    <script src="${url.resourcesPath}/js/menu-button-links.js" type="module"></script>
    <script type="module">
      import { startSessionPolling } from "${url.resourcesPath}/js/authChecker.js";
      startSessionPolling("${url.ssoLoginInOtherTabsUrl?no_esc}");
    </script>
    <#if authenticationSession??>
      <script type="module">
        import { checkAuthSession } from "${url.resourcesPath}/js/authChecker.js";
        checkAuthSession("${authenticationSession.authSessionIdHash}");
      </script>
    </#if>
  </#if>
</head>
<body class="${properties.kcBodyClass!'login-pf'}">
  <main id="kc-content" class="kc-gustav kc-auth-shell">
    <section class="kc-card kc-auth-card">
      <div class="kc-form-shell">
        <div class="kc-appearance"><button id="kc-theme-toggle" type="button">Darstellung wechseln</button></div>
        <#nested>
      </div>
    </section>
  </main>
</body>
</html>
</#macro>
