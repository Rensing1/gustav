<#import "_gustav_layout.ftl" as layout>
<@layout.document title=(msg("emailVerifyTitle"))>
<h1 class="kc-title">${msg("emailVerifyTitle")}</h1>

<#if message?has_content>
  <div class="kc-message kc-${message.type}">${message.summary}</div>
</#if>

<#if user?? && user.email?has_content>
  <p class="kc-hint">${msg("emailVerifyInstruction1", user.email)}</p>
<#else>
  <p class="kc-hint">${msg("emailVerifyInstruction2")}</p>
</#if>

<div class="kc-links">
  <#if url.loginAction?has_content>
    <a href="${url.loginAction}">${msg("doClickHere")}</a>
    <span> · </span>
  </#if>
  <#if url.loginUrl?has_content>
    <a href="${url.loginUrl}">${msg("doLogIn")}</a>
  </#if>
</div>
</@layout.document>
