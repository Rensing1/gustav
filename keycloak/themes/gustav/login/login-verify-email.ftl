<#import "_gustav_layout.ftl" as layout>
<@layout.document title=(msg("gustavVerifyWaitTitle"))>
<section data-verification-wait data-cooldown-template="${msg('emailVerifySendCooldown', '{seconds}')}" data-resend-success="${msg('gustavVerifyResent')}" data-resend-failure="${msg('gustavVerifyRetryError')}">
<h1 class="kc-title">${msg("gustavVerifyWaitTitle")}</h1>

<#-- Keep server errors, including resend cooldowns, visible and authoritative. -->
<#if message?has_content && message.type == 'error'>
  <div role="alert" data-verification-error class="kc-message kc-error">${message.summary}</div>
</#if>
<p class="kc-hint">${msg("gustavVerifyOpenMail")}</p>
<#if user?? && user.email?has_content>
  <p class="kc-verification-address">${user.email}</p>
</#if>
<p class="kc-hint">${msg("gustavVerifySpamHint")}</p>
<#-- Keycloak exposes verifyEmail after a successful send; never claim success on errors. -->
<#if verifyEmail?? && verifyEmail?has_content && !(message?has_content && message.type == 'error')>
  <noscript><p class="kc-message" role="status">${msg("gustavVerifySent")}</p></noscript>
</#if>
<p class="kc-message" data-resend-status role="status" hidden></p>

<div class="kc-links">
  <#if url.loginAction?has_content>
    <form data-verification-resend action="${url.loginAction}" method="post">
      <button class="kc-submit" type="submit">${msg("gustavVerifyResend")}</button>
    </form>
  </#if>
  <#if url.loginUrl?has_content>
    <a href="${url.loginUrl}">${msg("doLogIn")}</a>
  </#if>
</div>
</section>
<script src="${url.resourcesPath}/js/verify-email.js?v=${properties.gustavThemeVersion!'dev'}" defer></script>
</@layout.document>
