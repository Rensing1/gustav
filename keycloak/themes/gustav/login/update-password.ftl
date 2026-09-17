<#import "_gustav_layout.ftl" as layout>
<@layout.document title=(msg("updatePasswordTitle")!msg("doResetPassword"))>
<h1 class="kc-title">${msg("updatePasswordTitle")!msg("doResetPassword")}</h1>

  <#if message?has_content>
    <div class="kc-message kc-${message.type}">${message.summary}</div>
  </#if>

  <form id="kc-passwd-update-form" action="${url.loginAction}" method="post" class="kc-form">
    <#include "_password_requirements.ftl">
    <#-- Keycloak reports password-policy rejections as a global form error. -->
    <#assign passwordFieldError = messagesPerField.existsError('password', 'password-new')>
    <#assign passwordError = passwordFieldError || (message?has_content && message.type == 'error' && !messagesPerField.existsError('password-confirm'))>
    <label class="kc-field workspace-field" for="password-new">
      <span class="kc-label">${msg("password")}</span>
      <input class="kc-input" aria-invalid="${passwordError?c}" id="password-new" name="password-new" type="password" autocomplete="new-password" required aria-describedby="password-requirements password-new-error" autofocus>
      <#if passwordError><span id="password-new-error" class="kc-field-error" aria-live="polite"><#if passwordFieldError>${kcSanitize(messagesPerField.getFirstError('password', 'password-new'))?no_esc}<#else>${kcSanitize(message.summary)?no_esc}</#if></span></#if>
    </label>

    <label class="kc-field workspace-field" for="password-confirm">
      <span class="kc-label">${msg("passwordConfirm")}</span>
      <input class="kc-input" aria-invalid="${messagesPerField.existsError('password-confirm')?c}" id="password-confirm" name="password-confirm" type="password" autocomplete="new-password" required aria-describedby="password-requirements password-confirm-error">
      <#if messagesPerField.existsError('password-confirm')><span id="password-confirm-error" class="kc-field-error" aria-live="polite">${kcSanitize(messagesPerField.get('password-confirm'))?no_esc}</span></#if>
    </label>

    <button class="btn btn-primary kc-submit workspace-button" type="submit">${msg("doSubmit")}</button>
  </form>

  <div class="kc-links">
    <a href="${url.loginUrl}">${msg("doLogIn")}</a>
  </div>
</@layout.document>
