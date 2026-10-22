<#import "_gustav_layout.ftl" as layout>
<#assign info_title = msg("infoTitle", "Information")>
  <#if messageHeader?? && messageHeader?has_content>
    <#assign info_title = msg(messageHeader)>
  <#elseif message?has_content && message.summary?has_content>
    <#assign info_title = message.summary>
  </#if>
<#assign safe_required_actions = (requiredActions)![]>
<#assign has_required_actions = safe_required_actions?size gt 0>
<#assign specific_action = false>
<#assign action_label = msg("proceedWithAction")>
<#if safe_required_actions?size == 1>
  <#if safe_required_actions[0] == "VERIFY_EMAIL">
    <#assign specific_action = true>
    <#assign info_title = msg("gustavVerifyEmailTitle")>
    <#assign action_label = msg("gustavVerifyEmailAction")>
  <#elseif safe_required_actions[0] == "UPDATE_PASSWORD">
    <#assign specific_action = true>
    <#assign info_title = msg("updatePasswordTitle")>
    <#assign action_label = msg("gustavChoosePassword")>
  </#if>
</#if>
<@layout.document title=(info_title)>
<h1 class="kc-title">${info_title}</h1>

<#if message?has_content && message.summary != info_title && !(specific_action && message.summary == msg("confirmExecutionOfActions"))>
  <div role="status" class="kc-message kc-${message.type}">${message.summary}</div>
</#if>

<#if has_required_actions && !specific_action>
  <p class="kc-hint">
    <#list safe_required_actions as reqActionItem>
      ${msg("requiredAction.${reqActionItem}")}<#if reqActionItem_has_next>, </#if>
    </#list>
  </p>
</#if>

<#import "_gustav_error_components.ftl" as gustav_error>
<#assign client_base_url = (client.baseUrl)!"">
<#assign safe_page_redirect_uri = (pageRedirectUri)!"">
<#assign safe_action_uri = (actionUri)!"">
<#assign safe_login_url = (url.loginUrl)!"">
<#assign app_link = gustav_error.resolve_primary_app_link(
  safe_page_redirect_uri,
  client_base_url
)>

<#if !(skipLink??)>
  <div class="kc-links">
    <#if has_required_actions && safe_action_uri?has_content>
      <a class="kc-submit" href="${safe_action_uri}">${action_label}</a>
    <#elseif app_link?has_content>
      <a class="kc-submit" href="${app_link}">${msg("backToApplication")}</a>
    <#elseif safe_action_uri?has_content>
      <a class="kc-submit" href="${safe_action_uri}">${action_label}</a>
    <#elseif safe_login_url?has_content>
      <a class="kc-submit" href="${safe_login_url}">${msg("doLogIn")}</a>
    </#if>
  </div>
</#if>
</@layout.document>
