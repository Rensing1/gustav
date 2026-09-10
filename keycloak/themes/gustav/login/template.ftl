<#import "footer.ftl" as loginFooter>
<#import "_gustav_layout.ftl" as layout>
<#macro registrationLayout bodyClass="" displayInfo=false displayMessage=true displayRequiredFields=false>
<@layout.document title=msg("loginTitle",(realm.displayName!'')) sessionChecks=true>
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
</@layout.document>
</#macro>
