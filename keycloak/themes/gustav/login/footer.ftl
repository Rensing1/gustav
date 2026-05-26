<#macro content>
  <#local locale_supported = (locale.supported)![]>
  <#if (realm.internationalizationEnabled)!false && locale_supported?has_content && (locale_supported?size > 1)>
    <div class="kc-locale-links" aria-label="${msg("gustavLanguageLabel")}">
      <#list locale_supported as l>
        <a href="${l.url}" lang="${l.languageTag}">${l.label}</a><#if l_has_next><span> · </span></#if>
      </#list>
    </div>
  </#if>
</#macro>
