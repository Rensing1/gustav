<#-- Render the active IdP policy; never maintain a second password validator. -->
<div id="password-requirements" class="kc-password-requirements">
  <p>${msg("gustavPasswordRequirements")}</p>
  <ul>
    <#if (passwordPolicies.length!0) gt 0><li>${msg("gustavPasswordLength", passwordPolicies.length)}</li></#if>
    <#if (passwordPolicies.lowerCase!0) gt 0><li>${msg("gustavPasswordLower", passwordPolicies.lowerCase)}</li></#if>
    <#if (passwordPolicies.upperCase!0) gt 0><li>${msg("gustavPasswordUpper", passwordPolicies.upperCase)}</li></#if>
    <#if (passwordPolicies.digits!0) gt 0><li>${msg("gustavPasswordDigits", passwordPolicies.digits)}</li></#if>
    <#if (passwordPolicies.specialChars!0) gt 0><li>${msg("gustavPasswordSpecial", passwordPolicies.specialChars)}</li></#if>
  </ul>
</div>
