-- Ensure consistency between `visible` and `released_at`
-- When visible=true, released_at must be NOT NULL; when visible=false, released_at must be NULL.

alter table public.module_section_releases
  drop constraint if exists module_section_releases_visible_released_at_chk;

alter table public.module_section_releases
  add constraint module_section_releases_visible_released_at_chk
  check (
    (visible = true and released_at is not null)
    or (visible = false and released_at is null)
  );
