<#--
  Shared footer helpers for GUSTAV Keycloak error pages.
  Why:
  - Keep link rendering consistent between error templates.
  - Avoid duplicated separator logic and locale-link markup.
-->

<#function is_idp_account_link link="">
  <#if !(link?has_content)>
    <#return false>
  </#if>
  <#local normalized = link?lower_case>
  <#return normalized?contains("/realms/") && normalized?contains("/account/")>
</#function>

<#function resolve_primary_app_link pageRedirectUri="" clientBaseUrl="">
  <#-- Security/UX hardening: do not treat IdP account URLs as "back to app" target. -->
  <#if pageRedirectUri?has_content && !is_idp_account_link(pageRedirectUri)>
    <#return pageRedirectUri>
  </#if>
  <#if clientBaseUrl?has_content && !is_idp_account_link(clientBaseUrl)>
    <#return clientBaseUrl>
  </#if>
  <#return "">
</#function>

<#macro render_recovery_links appLink="">
  <div class="kc-links">
    <#assign has_item = false>
    <#if appLink?has_content>
      <a href="${appLink}">${msg("gustavBackToApp")}</a>
      <#assign has_item = true>
    </#if>
    <#if url?? && url.loginUrl?has_content>
      <#if has_item><span> · </span></#if>
      <a href="${url.loginUrl}">${msg("gustavTryLoginAgain")}</a>
      <#assign has_item = true>
    </#if>
    <#if realm?? && realm.registrationAllowed && url?? && url.registrationUrl?has_content>
      <#if has_item><span> · </span></#if>
      <a href="${url.registrationUrl}">${msg("doRegister")}</a>
      <#assign has_item = true>
    </#if>
  </div>
</#macro>

<#macro render_locale_links>
  <#if realm?? && realm.internationalizationEnabled && locale?? && locale.supported?has_content && (locale.supported?size > 1)>
    <div class="kc-locale-links" aria-label="${msg("gustavLanguageLabel")}">
      <#list locale.supported as l>
        <a href="${l.url}" lang="${l.languageTag}">${l.label}</a><#if l_has_next><span> · </span></#if>
      </#list>
    </div>
  </#if>
</#macro>
