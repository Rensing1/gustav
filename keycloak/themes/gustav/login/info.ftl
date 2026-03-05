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
  <link rel="stylesheet" href="${url.resourcesPath}/css/app-gustav-base.css">
  <link rel="stylesheet" href="${url.resourcesPath}/css/gustav.css">
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
    <section class="kc-card">
      <h1 class="kc-title">${info_title}</h1>

      <#if message?has_content>
        <div class="kc-message kc-${message.type}">${message.summary}</div>
      </#if>

      <#assign has_required_actions = requiredActions?? && requiredActions?size gt 0>
      <#if has_required_actions>
        <p class="kc-hint">
          <#list requiredActions as reqActionItem>
            ${msg("requiredAction.${reqActionItem}")}<#if reqActionItem_has_next>, </#if>
          </#list>
        </p>
      </#if>

      <#import "_gustav_error_components.ftl" as gustav_error>
      <#assign client_base_url = "">
      <#if client?? && client.baseUrl?has_content>
        <#assign client_base_url = client.baseUrl>
      </#if>
      <#assign app_link = gustav_error.resolve_primary_app_link(
        pageRedirectUri=(pageRedirectUri!""),
        clientBaseUrl=client_base_url
      )>

      <#if !(skipLink??)>
        <div class="kc-links">
          <#if has_required_actions && actionUri?has_content>
            <a href="${actionUri}">${msg("proceedWithAction")}</a>
          <#elseif app_link?has_content>
            <a href="${app_link}">${msg("backToApplication")}</a>
          <#elseif actionUri?has_content>
            <a href="${actionUri}">${msg("proceedWithAction")}</a>
          <#elseif url.loginUrl?has_content>
            <a href="${url.loginUrl}">${msg("doLogIn")}</a>
          </#if>
        </div>
      </#if>
    </section>
  </main>
</body>
</html>
