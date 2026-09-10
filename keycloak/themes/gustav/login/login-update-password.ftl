<#import "_gustav_layout.ftl" as layout>
<@layout.document title=(msg("updatePasswordTitle")!msg("doResetPassword"))>
<h1 class="kc-title">${msg("updatePasswordTitle")!msg("doResetPassword")}</h1>

  <#if message?has_content>
    <div class="kc-message kc-${message.type}">${message.summary}</div>
  </#if>

  <form id="kc-passwd-update-form" action="${url.loginAction}" method="post" class="kc-form">
    <label class="kc-field workspace-field" for="password-new">
      <span class="kc-label">${msg("password")}</span>
      <input class="kc-input" id="password-new" name="password-new" type="password" autocomplete="new-password" autofocus>
    </label>

    <label class="kc-field workspace-field" for="password-confirm">
      <span class="kc-label">${msg("passwordConfirm")}</span>
      <input class="kc-input" id="password-confirm" name="password-confirm" type="password" autocomplete="new-password">
    </label>

    <button class="btn btn-primary kc-submit workspace-button" type="submit">${msg("doSubmit")}</button>
  </form>

  <div class="kc-links">
    <a href="${url.loginUrl}">${msg("doLogIn")}</a>
  </div>
</@layout.document>
