export function asyncHandler(fn) {
  // Express 4 does not automatically handle rejected promises from async
  // handlers. Wrap them so errors propagate to the error middleware.
  return function wrapped(req, res, next) {
    Promise.resolve(fn(req, res, next)).catch(next);
  };
}

export function getMainLibraryUbername(metadata) {
  const machineName = metadata?.mainLibrary;
  const deps = metadata?.preloadedDependencies || [];
  const found = deps.find((d) => d.machineName === machineName);
  if (!machineName || !found) return null;
  return `${machineName} ${found.majorVersion}.${found.minorVersion}`;
}
