<#import "_gustav_layout.ftl" as layout>
<#assign page_title = msg("gustavAuthErrorTitle")>
<#assign token_error = false>
<#if message?has_content>
  <#list ["invalidCodeMessage", "expiredActionMessage", "expiredActionTokenNoSessionMessage", "expiredActionTokenSessionExistsMessage"] as key>
    <#if message.summary == msg(key)><#assign token_error = true></#if>
  </#list>
</#if>
<#if token_error><#assign page_title = msg("gustavInvalidLinkTitle")></#if>
<@layout.document title=(page_title)>
<h1 class="kc-title">${page_title}</h1>

<#if message?has_content>
  <div role="alert" class="kc-message kc-${message.type}">${message.summary}</div>
</#if>

<#if !message?has_content><p class="kc-hint">${msg("gustavAuthErrorGeneralHint")}</p></#if>

<#import "_gustav_error_components.ftl" as gustav_error>
<@gustav_error.render_recovery_links passwordHelp=token_error />
<@gustav_error.render_locale_links />
</@layout.document>
