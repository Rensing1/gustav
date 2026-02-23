<!DOCTYPE html>
<html lang="${(locale.currentLanguageTag)!'de'}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <#assign raw_summary = "">
  <#if message?has_content && message.summary?has_content>
    <#assign raw_summary = message.summary>
  </#if>
  <#assign summary_lc = raw_summary?lower_case>
  <#assign looks_like_expired = summary_lc?contains("expired_code") || summary_lc?contains("token") || summary_lc?contains("invalid code") || summary_lc?contains("ungültiger code")>
  <#assign page_title = msg("gustavAuthErrorTitle")>
  <#if looks_like_expired>
    <#assign page_title = msg("gustavAuthExpiredTitle")>
  </#if>
  <title>${page_title} - GUSTAV</title>
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
      <h1 class="kc-title">${page_title}</h1>

      <#if message?has_content>
        <div class="kc-message kc-${message.type}">${message.summary}</div>
      </#if>

      <#if looks_like_expired>
        <p class="kc-hint">${msg("gustavAuthErrorTokenHint")}</p>
      <#else>
        <p class="kc-hint">${msg("gustavAuthErrorCookieHint")}</p>
      </#if>

      <#assign app_link = "">
      <#if pageRedirectUri?has_content>
        <#assign app_link = pageRedirectUri>
      <#elseif client?? && client.baseUrl?has_content>
        <#assign app_link = client.baseUrl>
      <#elseif url.loginUrl?has_content>
        <#assign app_link = url.loginUrl>
      </#if>

      <div class="kc-links">
        <#if app_link?has_content>
          <a href="${app_link}">${msg("gustavBackToApp")}</a>
        </#if>
        <#if url.loginUrl?has_content>
          <#if app_link?has_content>
            <span> · </span>
          </#if>
          <a href="${url.loginUrl}">${msg("gustavTryLoginAgain")}</a>
        </#if>
        <#if realm.registrationAllowed && url.registrationUrl?has_content>
          <span> · </span>
          <a href="${url.registrationUrl}">${msg("doRegister")}</a>
        </#if>
      </div>

      <#if realm.internationalizationEnabled && locale.supported?has_content && (locale.supported?size > 1)>
        <div class="kc-locale-links" aria-label="Language">
          <#list locale.supported as l>
            <a href="${l.url}" lang="${l.languageTag}">${l.label}</a><#if l_has_next><span> · </span></#if>
          </#list>
        </div>
      </#if>
    </section>
  </main>
</body>
</html>
