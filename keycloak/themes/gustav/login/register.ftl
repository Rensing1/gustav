<#import "_gustav_layout.ftl" as layout>
<@layout.document title=(msg("doRegister"))>
<h1 class="kc-title">${msg("doRegister")}</h1>

  <#if message?has_content>
    <div class="kc-message kc-${message.type}">${message.summary}</div>
  </#if>

  <form id="kc-register-form" action="${url.registrationAction}" method="post" class="kc-form">
    <label class="kc-field workspace-field" for="display_name">
      <span class="kc-label">${msg("gustavDisplayName", "Wie möchtest du genannt werden?")}</span>
      <input class="kc-input" aria-invalid="${messagesPerField.existsError('display_name')?c}" aria-describedby="display_name-error" id="display_name" name="user.attributes.display_name" type="text" autocomplete="nickname" value="${(register.formData['user.attributes.display_name'])!''}" required>
      <#if messagesPerField.existsError('display_name')><span id="display_name-error" class="kc-field-error" aria-live="polite">${kcSanitize(messagesPerField.get('display_name'))?no_esc}</span></#if>
    </label>
    <!-- Simplified registration: use a single display name instead of separate first/last name fields -->

    <!-- Email is used as username; no separate username field -->

    <label class="kc-field workspace-field" for="email">
      <span class="kc-label">${msg("gustavSchoolEmailAddress")}</span>
      <input class="kc-input" aria-invalid="${messagesPerField.existsError('email')?c}" aria-describedby="email-error" id="email" name="email" type="email" autocomplete="email" required value="${(register.formData.email)!''}">
      <#if messagesPerField.existsError('email')><span id="email-error" class="kc-field-error" aria-live="polite">${kcSanitize(messagesPerField.get('email'))?no_esc}</span></#if>
    </label>

    <#if passwordRequired??>
    <#include "_password_requirements.ftl">
    <label class="kc-field workspace-field" for="password">
      <span class="kc-label">${msg("password")}</span>
      <input class="kc-input" aria-invalid="${messagesPerField.existsError('password')?c}" id="password" name="password" type="password" autocomplete="new-password" required aria-describedby="password-requirements password-error">
      <#if messagesPerField.existsError('password')><span id="password-error" class="kc-field-error" aria-live="polite">${kcSanitize(messagesPerField.get('password'))?no_esc}</span></#if>
    </label>

    <label class="kc-field workspace-field" for="password-confirm">
      <span class="kc-label">${msg("passwordConfirm")}</span>
      <input class="kc-input" aria-invalid="${messagesPerField.existsError('password-confirm')?c}" id="password-confirm" name="password-confirm" type="password" autocomplete="new-password" required aria-describedby="password-requirements password-confirm-error">
      <#if messagesPerField.existsError('password-confirm')><span id="password-confirm-error" class="kc-field-error" aria-live="polite">${kcSanitize(messagesPerField.get('password-confirm'))?no_esc}</span></#if>
    </label>

    </#if>
    <button class="btn btn-primary kc-submit workspace-button" type="submit">${msg("doRegister")}</button>
  </form>

  <div class="kc-links">
    <a href="${url.loginUrl}">${msg("doLogIn")}</a>
  </div>
</@layout.document>
