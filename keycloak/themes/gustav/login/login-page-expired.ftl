<#import "_gustav_layout.ftl" as layout>
<#assign page_title = msg("gustavAuthExpiredTitle")>
<@layout.document title=(page_title)>
<h1 class="kc-title">${page_title}</h1>

<#if message?has_content>
  <div class="kc-message kc-${message.type}">${message.summary}</div>
</#if>

<p class="kc-hint">${msg("gustavAuthErrorTokenHint")}</p>

<#import "_gustav_error_components.ftl" as gustav_error>
<@gustav_error.render_recovery_links />
<@gustav_error.render_locale_links />
</@layout.document>
