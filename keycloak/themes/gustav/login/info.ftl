<!DOCTYPE html>
<html lang="${(locale.currentLanguageTag)!'de'}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <#assign info_title = msg("infoTitle", "Information")>
  <#if messageHeader?? && messageHeader?has_content>
    <#assign info_title = messageHeader>
  <#elseif message?has_content && message.summary?has_content>
    <#assign info_title = message.summary>
  </#if>
  <title>${info_title} - GUSTAV</title>
  <link rel="stylesheet" href="${url.resourcesPath}/css/auth-theme.css?v=${properties.gustavThemeVersion!"dev"}">
  <link rel="stylesheet" href="${url.resourcesPath}/css/gustav.css?v=${properties.gustavThemeVersion!"dev"}">
  <script>
    (function(){
      try {
        var saved = localStorage.getItem('gustav-theme');
        if (saved === 'everforest-dark-hard' || saved === 'rose-pine-dawn') {
          document.documentElement.setAttribute('data-theme', saved);
        }
      } catch (e) { /* ignore */ }
    })();
  </script>
</head>
<body class="login-pf">
  <main id="kc-content" class="kc-gustav">
    <div class="kc-auth-shell">
    <section class="kc-card">
      <div class="kc-auth-card">
      <h1 class="kc-title">${info_title}</h1>

      <#if message?has_content>
        <div class="kc-message kc-${message.type}">${message.summary}</div>
      </#if>

      <#assign safe_required_actions = (requiredActions)![]>
      <#assign has_required_actions = safe_required_actions?size gt 0>
      <#if has_required_actions>
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
            <a href="${safe_action_uri}">${msg("proceedWithAction")}</a>
          <#elseif app_link?has_content>
            <a href="${app_link}">${msg("backToApplication")}</a>
          <#elseif safe_action_uri?has_content>
            <a href="${safe_action_uri}">${msg("proceedWithAction")}</a>
          <#elseif safe_login_url?has_content>
            <a href="${safe_login_url}">${msg("doLogIn")}</a>
          </#if>
        </div>
      </#if>
      </div>
    </section>
    </div>
  </main>
</body>
</html>
