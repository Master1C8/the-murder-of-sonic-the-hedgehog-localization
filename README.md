# The Murder of Sonic the Hedgehog — мультипатч VN Revival

Нативный macOS-установщик единого пакета всех 30 неанглийских локалей VN
Revival. Он адаптирован из проверенного установщика Stardew Valley, но вместо
SMAPI и Content Patcher работает с точным списком Unity-файлов игры.

Английские исходные ассеты извлечены в JSON, CSV и контекстные пакеты под
`Documentation/Localization/Source/en`. Все 30 текстовых локализаций и
подготовленные шрифты входят в проверяемый payload; пользователь выбирает
активный язык в установщике и может сменить его повторным запуском. Десять
текстовых PNG пока намеренно остаются английскими (`imagesModified=false`).
Французский патч ChaosTrad использован только для технического исследования и
не входит в репозиторий.

## Что реализовано

- автоматическое обнаружение Steam-версии на macOS через
  `steamapps/libraryfolders.vdf`, включая дополнительные библиотеки;
- чтение `appmanifest_2324650.acf` и проверка App ID `2324650` и каталога
  установки; сборка `20535215` остаётся эталоном payload, но более новая
  Steam-сборка принимается, если все затрагиваемые файлы сохранили точные
  совместимые SHA-256;
- ручной выбор папки оставлен как запасной путь и принимает только игру,
  связанную с корректным Steam-манифестом;
- строгий канонический набор из 30 siteLocale и 30 уникальных runtime-кодов;
- одна сборка с выбором любой из 30 локалей перед установкой;
- английский интерфейс установщика независимо от выбранного языка игры;
- повторный запуск безопасно переключает активный язык;
- компактные двухступенчатые xdelta-цепочки вместо 30 полных копий Unity-файлов;
- декларативные SHA-256 оригинала, каждой дельты и итогового файла;
- отказ от перезаписи неизвестно изменённых игровых файлов;
- безопасная повторная установка после обновления Steam: восстановленные
  неизменившиеся оригиналы и удалённые принадлежащие VN Revival файлы
  устанавливаются заново, а обновление, изменившее нужный Unity-файл,
  останавливается до замены игровых данных;
- строгая миграция прежней `dev-russian-runtime` установки только при полном
  совпадении её квитанции, установленных SHA-256 и оригинальных резервных копий;
- постоянная проверяемая резервная копия оригиналов;
- staging, журнал транзакции, rollback после ошибки или прерывания;
- безопасное повторное обновление только файлов нашего пакета;
- запуск игры через Steam после успешной установки;
- оригинальная иконка игры из macOS Steam-сборки;
- воспроизводимое извлечение 3547 английских единиц и 72 PNG-кандидатов без
  изменения установленной игры;
- отдельная локализация отображаемых имён и названий локаций без изменения
  служебных Ink/managed-ID; единый контракт действует для всех 30 локалей;
- unit-тесты на временной фиктивной игре — настоящая установка не затрагивается.

## Пересборка payload

`Scripts/build-unified-payload.py` пересобирает все 30 полных локальных
вариантов из проверенного оригинала, упаковывает русский базовый слой и 29
дельт, затем разворачивает каждую дельту обратно и сверяет итоговый SHA-256.
Только после успешной проверки скрипт атомарно заменяет
`Resources/LocalizationPayload` и выставляет readiness в `PackageConfig.json`.
Финальный gate и сборка приложения выполняются командой
`./Scripts/release-audit.sh`.

## Windows release build

The Windows release uses one shared managed runtime instead of rebuilding the
same compressed Unity bundles 30 times. It loads stable-path Ink stories,
context-aware UI translations, complex-script shaping data, and privately
registered locale fonts from external files. All 30 locales are installed in
one 71.77 MiB payload; textures remain unchanged. Build and verify it with:

```sh
PYTHONPYCACHEPREFIX=/private/tmp/sonic-pyc \
python3 Scripts/build-windows-runtime-payload.py \
  --managed-root .build/windows-baseline/Managed \
  --xdelta /opt/homebrew/bin/xdelta3 \
  --windows-xdelta .build/tooling/xdelta-windows-build/xdelta3.exe \
  --xdelta-license .build/tooling/xdelta-src/xdelta3/LICENSE

PYTHONPYCACHEPREFIX=/private/tmp/sonic-pyc \
python3 Scripts/test-windows-runtime-payload.py
./Scripts/build-windows-installer.sh
```

The result is written to `Windows/VN Revival Sonic Installer.exe` and uses the
single payload copy in `Windows/Resources`. Run
`Scripts/test-windows-installer.ps1` inside Windows against the `Windows`
folder and `.build/windows-baseline`; the harness creates and removes its own
temporary fake Steam library and never targets the installed game. It covers
legacy-layout migration, three locale selections, a compatible Steam-update
reapply, transactional ownership, and foreign-modification refusal.

Канонический набор: `zh`, `ru`, `es`, `es-419`, `pt-BR`, `ja`, `de`, `ko`,
`fr`, `tr`, `pl`, `zh-TW`, `it`, `th`, `vi`, `id`, `uk`, `ar`, `cs`, `hu`,
`nl`, `fa`, `ro`, `hi`, `fil`, `el`, `bg`, `sr`, `sw`, `he`. Английский `en`
остаётся исходным языком игры и не считается отдельным пакетом локализации.

Установщик предлагает выбрать одну из 30 локалей перед началом работы. Все 30
вариантов находятся в одной сборке приложения; к игровым файлам применяется
выбранный вариант, а `siteLocale` и `runtimeCode` атомарно сохраняются в
квитанции установки.

Французский архив показывает минимум следующие поверхности локализации:
`level0`, `Managed/Assembly-CSharp.dll`, `sharedassets0.assets`, Addressables
`catalog.json`, основной dialog/UI bundle, inventory bundle, изображения и
шесть шрифтов. Имена bundle зависят от платформы и сборки, поэтому их нельзя
копировать из французского Windows-пакета в macOS-манифест.

## Безопасная разработка

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
CLANG_MODULE_CACHE_PATH=/private/tmp/murder-sonic-installer-swift-cache \
swift test --disable-sandbox

ALLOW_INCOMPLETE_PAYLOAD=1 ./Scripts/release-audit.sh
```

Не открывайте собранное приложение на реальной системе только для просмотра
интерфейса: установка начинается после подтверждения выбранного языка.

Служебные идентификаторы, команды и разделители никогда не переводятся.
Обязательный технический стандарт локалей описан в
`Documentation/Localization/RUNTIME_IDENTIFIERS.md` и проверяется release-аудитом.
Редакторская приёмка выполняется по
`Documentation/Localization/AUDIT_WORKFLOW.md`: один полный семантический
аудит, затем проверка изменённых единиц и их зависимостей, обязательный набор
регрессий и полный машинный gate всего корпуса.

## Происхождение основы и исследования

- Основа UX и SwiftUI-сборки: StardewTranslationInstaller, commit
  `0c90756441f2b62bfe8df4ddf08d4ed98447cf04`.
- Иконка: `PlayerIcon.icns` из установленной macOS Steam-сборки игры,
  SHA-256 `285d1b9f42a65d2c77d919d10c04794c3a6ca72439ed7dd2b08f4f2861d060b8`.
- Технический образец Unity-патча: ChaosTrad, Le Meurtre de Sonic, версия 1.0
  (октябрь 2023). Файлы образца не распространяются этим проектом.
