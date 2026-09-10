<#import "_gustav_layout.ftl" as layout>
<@layout.document title=(msg("doForgotPassword"))>
<h1 class="kc-title">${msg("doForgotPassword")}</h1>

  <#if message?has_content>
    <div class="kc-message kc-${message.type}">${message.summary}</div>
  </#if>

  <form id="kc-reset-password-form" action="${url.loginAction}" method="post" class="kc-form">
    <label class="kc-field workspace-field" for="username">
      <span class="kc-label">${msg("gustavEmailAddress")}</span>
      <input class="kc-input" id="username" name="username" type="email" autocomplete="email" autofocus>
    </label>
    <button class="btn btn-primary kc-submit workspace-button" type="submit">${msg("doSubmit")}</button>
  </form>

  <div class="kc-links">
    <a href="${url.loginUrl}">${msg("doLogIn")}</a>
    <#if realm.registrationAllowed>
      <span> · </span>
      <a href="${url.registrationUrl}">${msg("doRegister")}</a>
    </#if>
  </div>
</@layout.document>
