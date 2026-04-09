<#import "footer.ftl" as loginFooter>
<#macro registrationLayout bodyClass="" displayInfo=false displayMessage=true displayRequiredFields=false>
<!DOCTYPE html>
<html lang="${lang}">
<head>
  <meta charset="utf-8">
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${msg("loginTitle",(realm.displayName!''))} - GUSTAV</title>
  <link rel="stylesheet" href="${url.resourcesPath}/css/auth-theme.css?v=${properties.gustavThemeVersion!"dev"}">
  <link rel="stylesheet" href="${url.resourcesPath}/css/gustav.css?v=${properties.gustavThemeVersion!"dev"}">
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
  <script>
    (function(){
      try {
        var saved = localStorage.getItem('gustav-theme');
        if (saved === 'dark' || saved === 'everforest-dark-hard' || saved === 'rose-pine-dawn') {
          document.documentElement.setAttribute('data-theme', saved === 'dark' ? 'dark' : saved);
        }
      } catch (e) { /* ignore */ }
    })();
  </script>
  <script type="importmap">
    {
      "imports": {
        "rfc4648": "${url.resourcesCommonPath}/vendor/rfc4648/rfc4648.js"
      }
    }
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
</head>
<body class="${properties.kcBodyClass!}">
  <main class="${properties.kcLoginClass!}">
    <section class="${properties.kcFormCardClass!}">
      <div class="${properties.kcContentWrapperClass!}">
        <header class="${properties.kcFormHeaderClass!}">
          <#if !(auth?has_content && auth.showUsername() && !auth.showResetCredentials())>
            <#if displayRequiredFields>
              <p class="kc-auth-eyebrow">${msg("requiredFields")}</p>
            </#if>
            <h1 id="kc-page-title" class="kc-title"><#nested "header"></h1>
          <#else>
            <#nested "show-username">
            <div id="kc-username" class="kc-user-chip">
              <span class="kc-user-chip__value">${auth.attemptedUsername}</span>
              <a id="reset-login" class="kc-user-chip__reset" href="${url.loginRestartFlowUrl}" aria-label="${msg("restartLoginTooltip")}">
                ${msg("gustavResetFlowLabel")}
              </a>
            </div>
          </#if>
        </header>

        <#if displayMessage && message?has_content && (message.type != 'warning' || !isAppInitiatedAction??)>
          <div class="kc-message kc-${message.type}">
            <span class="${properties.kcAlertTitleClass!}">${kcSanitize(message.summary)?no_esc}</span>
          </div>
        </#if>

        <#nested "form">

        <#if auth?has_content && auth.showTryAnotherWayLink()>
          <form id="kc-select-try-another-way-form" action="${url.loginAction}" method="post" class="${properties.kcFormClass!}">
            <input type="hidden" name="tryAnotherWay" value="on"/>
            <div class="kc-links">
              <a href="#" id="try-another-way" onclick="document.forms['kc-select-try-another-way-form'].requestSubmit();return false;">${msg("doTryAnotherWay")}</a>
            </div>
          </form>
        </#if>

        <#nested "socialProviders">

        <#if displayInfo>
          <div id="kc-info" class="${properties.kcSignUpClass!}">
            <div id="kc-info-wrapper" class="${properties.kcInfoAreaWrapperClass!}">
              <#nested "info">
            </div>
          </div>
        </#if>

        <@loginFooter.content />
      </div>
    </section>
  </main>
</body>
</html>
</#macro>
