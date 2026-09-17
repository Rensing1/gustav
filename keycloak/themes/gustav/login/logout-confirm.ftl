<#import "_gustav_layout.ftl" as layout>
<@layout.document title=(msg("gustavLogoutConfirmTitle"))>
<h1 class="kc-title">${msg("gustavLogoutConfirmTitle")}</h1>
  <p class="kc-hint">${msg("gustavLogoutConfirmHint")}</p>

  <#if message?has_content>
    <div class="kc-message kc-${message.type}">${message.summary}</div>
  </#if>

  <form id="kc-logout-confirm" class="kc-form" action="${url.logoutConfirmAction}" method="post">
    <input type="hidden" name="session_code" value="${logoutConfirm.code}">
    <button class="btn btn-primary kc-submit workspace-button" type="submit">
      ${msg("gustavLogoutConfirmSubmit")}
    </button>
  </form>

  <#import "_gustav_error_components.ftl" as gustav_error>
  <#assign client_base_url = (client.baseUrl)!"">
  <#assign safe_page_redirect_uri = (pageRedirectUri)!"">
  <#assign app_link = gustav_error.resolve_primary_app_link(
    safe_page_redirect_uri,
    client_base_url
  )>
  <#if app_link?has_content>
    <div class="kc-links">
      <a href="${app_link}">${msg("gustavBackToApp")}</a>
    </div>
  </#if>
  <@gustav_error.render_locale_links />
</@layout.document>
