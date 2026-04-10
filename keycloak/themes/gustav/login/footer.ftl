<#macro content>
  <#if realm.internationalizationEnabled && locale.supported?has_content && (locale.supported?size > 1)>
    <div class="kc-locale-links" aria-label="${msg("gustavLanguageLabel")}">
      <#list locale.supported as l>
        <a href="${l.url}" lang="${l.languageTag}">${l.label}</a><#if l_has_next><span> · </span></#if>
      </#list>
    </div>
  </#if>
</#macro>
