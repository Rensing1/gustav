<#-- Render the active IdP policy; never maintain a second password validator. -->
<div id="password-requirements" class="kc-password-requirements">
  <p>${msg("gustavPasswordRequirements")}</p>
  <ul>
    <#if passwordPolicies.length??><li>${msg("gustavPasswordLength", passwordPolicies.length)}</li></#if>
    <#if passwordPolicies.lowerCase??><li>${msg("gustavPasswordLower", passwordPolicies.lowerCase)}</li></#if>
    <#if passwordPolicies.upperCase??><li>${msg("gustavPasswordUpper", passwordPolicies.upperCase)}</li></#if>
    <#if passwordPolicies.digits??><li>${msg("gustavPasswordDigits", passwordPolicies.digits)}</li></#if>
    <#if passwordPolicies.specialChars??><li>${msg("gustavPasswordSpecial", passwordPolicies.specialChars)}</li></#if>
  </ul>
</div>
