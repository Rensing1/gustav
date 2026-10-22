<#import "_gustav_layout.ftl" as layout>
<#-- Keycloak uses the login page to acknowledge reset mail requests. -->
<#assign mail_sent = message?has_content && message.summary == msg("emailSentMessage")>
<#assign page_title = msg("doLogIn")>
<#if mail_sent><#assign page_title = msg("gustavCheckInbox")></#if>
<@layout.document title=(page_title)>
<h1 class="kc-title">${page_title}</h1>

  <#if message?has_content>
    <div role="status" class="kc-message kc-${message.type}">${message.summary}</div>
  </#if>

  <#if !mail_sent>
  <form id="kc-form-login" action="${url.loginAction}" method="post" class="kc-form">
    <label class="kc-field workspace-field" for="username">
      <span class="kc-label">${msg("gustavEmailAddress")}</span>
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
  </#if>

  <div class="kc-links">
    <#if realm.resetPasswordAllowed>
      <a href="${url.loginResetCredentialsUrl}"><#if mail_sent>${msg("gustavRequestAgain")}<#else>${msg("doForgotPassword")}</#if></a>
    </#if>
    <#if mail_sent>
      <a href="${url.loginUrl}">${msg("doLogIn")}</a>
    <#elseif realm.registrationAllowed>
      <a href="${url.registrationUrl}">${msg("doRegister")}</a>
    </#if>
  </div>
</@layout.document>
