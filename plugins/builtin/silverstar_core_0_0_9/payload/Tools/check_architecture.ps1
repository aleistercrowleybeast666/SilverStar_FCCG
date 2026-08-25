$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$script:checkCount = 0
$script:failures = New-Object 'System.Collections.Generic.List[string]'

function Add-ArchitectureFailure {
    param([Parameter(Mandatory = $true)][string]$Message)

    $script:failures.Add($Message)
}

function Assert-ArchitectureCondition {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )

    $script:checkCount++
    if (-not $Condition) {
        Add-ArchitectureFailure -Message $Message
    }
}

function Get-ArchitectureFiles {
    param(
        [Parameter(Mandatory = $true)][string[]]$Paths,
        [string[]]$Extensions = @('.c', '.h')
    )

    $files = @()
    foreach ($relativePath in $Paths) {
        $path = Join-Path $repoRoot $relativePath
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            $item = Get-Item -LiteralPath $path
            if ($Extensions -contains $item.Extension) {
                $files += $item
            }
        }
        elseif (Test-Path -LiteralPath $path -PathType Container) {
            $files += Get-ChildItem -LiteralPath $path -Recurse -File |
                Where-Object { $Extensions -contains $_.Extension }
        }
        else {
            Add-ArchitectureFailure -Message "Architecture scope is missing: $relativePath"
        }
    }
    return @($files | Sort-Object -Property FullName -Unique)
}

function Assert-NoArchitecturePattern {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$Paths,
        [Parameter(Mandatory = $true)][string]$Pattern,
        [string[]]$Extensions = @('.c', '.h')
    )

    $script:checkCount++
    $files = Get-ArchitectureFiles -Paths $Paths -Extensions $Extensions
    $diagnostics = @()
    foreach ($file in $files) {
        $matches = @(Select-String -LiteralPath $file.FullName -Pattern $Pattern)
        foreach ($match in $matches) {
            if ($diagnostics.Count -lt 8) {
                $relative = $file.FullName.Substring($repoRoot.Length + 1)
                $diagnostics += ("{0}:{1}: {2}" -f $relative,
                    $match.LineNumber, $match.Line.Trim())
            }
        }
    }
    if ($diagnostics.Count -ne 0) {
        Add-ArchitectureFailure -Message (
            "$Name`n  " + ($diagnostics -join "`n  "))
    }
}

function Assert-FileContainsPattern {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$Pattern,
        [Parameter(Mandatory = $true)][string]$Message
    )

    $script:checkCount++
    $path = Join-Path $repoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Add-ArchitectureFailure -Message "Missing required file: $RelativePath"
        return
    }
    $content = Get-Content -Raw -LiteralPath $path
    if ($content -notmatch $Pattern) {
        Add-ArchitectureFailure -Message $Message
    }
}

function Assert-PathAbsent {
    param([Parameter(Mandatory = $true)][string]$RelativePath)

    Assert-ArchitectureCondition `
        -Condition (-not (Test-Path -LiteralPath (Join-Path $repoRoot $RelativePath))) `
        -Message "Legacy architecture path still exists: $RelativePath"
}

function Get-YamlListValues {
    param(
        [Parameter(Mandatory = $true)][string]$Content,
        [Parameter(Mandatory = $true)][string]$BlockPattern,
        [Parameter(Mandatory = $true)][string]$ItemPattern
    )

    $block = [regex]::Match($Content, $BlockPattern)
    if (-not $block.Success) {
        return @()
    }
    $values = @()
    foreach ($line in ($block.Groups['items'].Value -split '\r?\n')) {
        if ($line -match $ItemPattern) {
            $values += $Matches['value'].Trim().Trim('"').Trim("'")
        }
    }
    return @($values)
}

function ConvertTo-ArchitecturePath {
    param([Parameter(Mandatory = $true)][string]$Path)

    return ($Path -replace '\\', '/')
}

$portableCodePaths = @(
    'System', 'Algorithm', 'Protocol', 'Devices', 'Interfaces', 'Modules',
    'Common', 'Platform\Inc', 'Board', 'FlightLogic'
)
$firstPartyRuntimePaths = @(
    'APP', 'Algorithm', 'Board', 'Common', 'Devices', 'FlightLogic',
    'Generated', 'Interfaces', 'Modules', 'OS', 'Platform', 'Protocol',
    'System', 'Targets'
)
$systemLayerPaths = @(
    'System', 'Algorithm', 'FlightLogic', 'Protocol', 'Interfaces', 'Modules'
)
$deviceCorePaths = @(
    'Devices\IMU\JY901B\Inc',
    'Devices\IMU\JY901B\Src',
    'Devices\GNSS\NEO_M9N\Inc',
    'Devices\GNSS\NEO_M9N\Src',
    'Devices\Telemetry\SX1281\Inc',
    'Devices\Telemetry\SX1281\Src',
    'Devices\Console\UART\Inc',
    'Devices\Console\UART\Src'
)

$vendorPattern = '(?i)\bHAL_[A-Za-z0-9_]*|\bstm32[A-Za-z0-9_]*|' +
    '\bGPIO_TypeDef\b|\bUART_HandleTypeDef\b|\bSPI_HandleTypeDef\b|' +
    '\bDMA_HandleTypeDef\b|\bI2C_HandleTypeDef\b|\bGPIO[A-K]\b|' +
    '\bGPIO_PIN_[A-Za-z0-9_]+\b|\bhuart[0-9]*\b|\bhspi[0-9]*\b|' +
    '\bhi2c[0-9]*\b|\bhadc[0-9]*\b|cmsis_gcc|cmsis_os'
Assert-NoArchitecturePattern -Name `
    'Vendor types or MCU symbols leaked above Platform/Target/CubeMX boundaries.' `
    -Paths $portableCodePaths -Pattern $vendorPattern

Assert-NoArchitecturePattern -Name `
    'System-facing layers reference a concrete sensor or radio implementation.' `
    -Paths $systemLayerPaths `
    -Pattern '(?i)\bJY901B\b|\bNEO[_-]?M9N\b|\bSX128[01]\b|#include\s*[<"](?:jy901b|neo_m9n|sx128)'

Assert-NoArchitecturePattern -Name `
    'MCU Platform references a concrete sensor or radio implementation.' `
    -Paths @('Platform') `
    -Pattern '(?i)\bJY901B\b|\bNEO[_-]?M9N\b|\bSX128[01]\b'

Assert-NoArchitecturePattern -Name `
    'MCU Platform includes a concrete Board or Target header.' `
    -Paths @('Platform') `
    -Pattern '#include\s*[<"](?:Board|Targets)[/\\]'

Assert-NoArchitecturePattern -Name `
    'A Device Adapter depends directly on STM32, HAL, a concrete Board, or a concrete Target.' `
    -Paths @(
        'Devices\IMU\JY901B\Adapter',
        'Devices\GNSS\NEO_M9N\Adapter',
        'Devices\Telemetry\SX1281\Adapter',
        'Devices\Console\UART\Adapter'
    ) -Pattern ('(?i)\bHAL_[A-Za-z0-9_]*|\bstm32[A-Za-z0-9_]*|' +
        '#include\s*[<"](?:Board|Targets)[/\\]|\bUART_HandleTypeDef\b|' +
        '\bSPI_HandleTypeDef\b')

Assert-NoArchitecturePattern -Name `
    'Device core depends on a System interface instead of native data plus Platform.' `
    -Paths $deviceCorePaths `
    -Pattern '#include\s*[<"]system_[A-Za-z0-9_./-]*[>"]'

Assert-NoArchitecturePattern -Name `
    'Portable System/Device/Protocol code depends on FreeRTOS.' `
    -Paths $portableCodePaths `
    -Pattern '#include\s*[<"](?:FreeRTOS|task|queue|semphr|timers)\.h[>"]'

Assert-NoArchitecturePattern -Name `
    'Legacy Provider/VTable/callback architecture remains in first-party runtime code.' `
    -Paths $firstPartyRuntimePaths `
    -Pattern ('(?i)\b[A-Za-z0-9_]*ProviderOps\b|\bprovider\b|' +
        'RegisterCallback|DioIrqHandler|\bRadio\s*\.')

Assert-NoArchitecturePattern -Name `
    'CMSIS-RTOS2 or defaultTask remains in first-party application code.' `
    -Paths @('APP', 'Core', 'OS', 'System', 'Devices', 'Platform') `
    -Pattern ('(?i)\bcmsis_os2?\b|\bosThread[A-Za-z0-9_]*\b|' +
        '\bosDelay\b|\bosKernel[A-Za-z0-9_]*\b|\bdefaultTask\b|' +
        '\bStartDefaultTask\b')

Assert-NoArchitecturePattern -Name `
    'Dynamic allocation API remains in first-party runtime code.' `
    -Paths $firstPartyRuntimePaths `
    -Pattern '(?i)\b(?:malloc|calloc|realloc|free|pvPortMalloc|vPortFree)\s*\('

Assert-NoArchitecturePattern -Name `
    'A libc printf formatter remains in first-party runtime code.' `
    -Paths $firstPartyRuntimePaths `
    -Pattern '(?i)\b(?:snprintf|vsnprintf|sprintf|vsprintf)\s*\('

Assert-NoArchitecturePattern -Name `
    'A non-static FreeRTOS object creation API remains in first-party code.' `
    -Paths @('APP', 'OS', 'Core') `
    -Pattern '\bxTaskCreate\s*\(|\bxQueueCreate\s*\(|\bxSemaphoreCreate(?:Binary|Mutex|Counting)\s*\('

Assert-NoArchitecturePattern -Name `
    'The removed 32-bit log mask or fixed Provider metadata array remains.' `
    -Paths @('APP', 'System', 'Protocol', 'Interfaces', 'Generated') `
    -Pattern ('SYSTEM_LOG_MASK_|provider_ids\s*\[|algorithm_ids\s*\[|' +
        'log_decimation\s*\[')

Assert-NoArchitecturePattern -Name `
    'Semtech/SX1281 runtime callback or Radio vtable remains.' `
    -Paths @('Devices\Telemetry\SX1281', 'Middlewares\Third_Party\SX1280lib') `
    -Pattern 'RegisterCallback|DioIrqHandler|\bRadio\s*\.|#include\s*[<"]radio\.h[>"]'

$legacyPaths = @(
    'System\Inc\Interfaces',
    'System\Inc\system_device_registry.h',
    'System\Src\system_device_registry.c',
    'System\User\system_user_registry.h',
    'Core\Src\freertos.c',
    'Core\Inc\FreeRTOSConfig.h',
    'Middlewares\Third_Party\FreeRTOS\Source',
    'Middlewares\Third_Party\SX1280lib\radio.h',
    'Devices\IMU\JY901B\Src\jy901b_port_stm32.c',
    'Devices\GNSS\NEO_M9N\Src\neo_m9n_port_stm32.c',
    'Devices\Telemetry\SX1281\Src\sx1281_port_stm32.c',
    'Bindings',
    'Board\SilverStar_F407',
    'Protocol\SSLOG\generated',
    'Tools\generate_sslog.py'
)
foreach ($legacyPath in $legacyPaths) {
    Assert-PathAbsent -RelativePath $legacyPath
}

$generatedFiles = @(Get-ChildItem -LiteralPath `
    (Join-Path $repoRoot 'Generated') -Recurse -File |
    ForEach-Object { $_.FullName.Substring($repoRoot.Length + 1) } |
    Sort-Object)
$expectedGeneratedFiles = @(
    'Generated\Inc\project_log_config.h',
    'Generated\Inc\project_resources.h',
    'Generated\Src\platform_resources.c',
    'Generated\Src\project_log_config.c',
    'Generated\Src\project_metadata.c',
    'Generated\Inc\project_capability_routes.h',
    'Generated\Src\project_capability_routes.c',
    'Generated\Inc\project_flight_config.h',
    'Generated\project_sources.mk',
    'Generated\module.mk'
) | Sort-Object
$generatedDifference = @(Compare-Object `
    -ReferenceObject $expectedGeneratedFiles -DifferenceObject $generatedFiles)
Assert-ArchitectureCondition -Condition ($generatedDifference.Count -eq 0) `
    -Message ('Generated contains files outside the reviewed thin-glue set: ' +
        ($generatedFiles -join ', '))
Assert-NoArchitecturePattern -Name `
    'Generated glue contains flight decisions or algorithm implementation.' `
    -Paths @('Generated') `
    -Pattern ('\bFlightDeployment_|\bFlightLanding_|\bNavigationKf_|' +
        '\bInsMechanization_|\bSystemLifecycle_(?:Process|Enter)')

$manifestFiles = @('Makefile') + @(
    Get-ChildItem -LiteralPath (Join-Path $repoRoot 'BuildSystem'),
        (Join-Path $repoRoot 'Targets'), (Join-Path $repoRoot 'Platform'),
        (Join-Path $repoRoot 'Devices'), (Join-Path $repoRoot 'Board'),
        (Join-Path $repoRoot 'FlightLogic'), (Join-Path $repoRoot 'Generated') `
        -Recurse -File -Filter '*.mk' |
        ForEach-Object { $_.FullName.Substring($repoRoot.Length + 1) }
)
Assert-NoArchitecturePattern -Name `
    'Authoritative build manifests use wildcard scanning or object flattening.' `
    -Paths $manifestFiles -Extensions @('.mk', '') `
    -Pattern '\$\(\s*(?:wildcard|notdir)\b|[*?]\.c\b'

Assert-NoArchitecturePattern -Name `
    'The authoritative source graph still contains the CubeMX C heap backend.' `
    -Paths $manifestFiles -Extensions @('.mk', '') `
    -Pattern '(?i)Core[/\\]Src[/\\]sysmem\.c|heap_[1-5]\.c'

Assert-NoArchitecturePattern -Name `
    'Authoritative build manifests invoke Python or the removed SSLOG generator.' `
    -Paths $manifestFiles -Extensions @('.mk', '') `
    -Pattern '(?i)\bpython(?:3)?(?:\.exe)?\b|\bpy(?:\.exe)?\b|generate_sslog'

Assert-NoArchitecturePattern -Name `
    'FatFs retains a dynamic allocation hook.' `
    -Paths @('FATFS\Target\ffconf.h') `
    -Pattern '(?i)\b(?:pvPortMalloc|vPortFree|ff_malloc|ff_free)\b'

Assert-FileContainsPattern -RelativePath 'Makefile' `
    -Pattern 'TARGET\s*:=\s*SilverStar_0_0_9' `
    -Message 'Authoritative firmware target is not SilverStar_0_0_9.'
Assert-FileContainsPattern -RelativePath 'Makefile' `
    -Pattern 'BUILD_ROOT\s*:=\s*build/\$\(TARGET_PROFILE\)/\$\(CONFIG\)' `
    -Message 'Build output is not partitioned by target and configuration.'
Assert-FileContainsPattern -RelativePath 'Makefile' `
    -Pattern 'C_OBJECTS\s*:=\s*\$\(addprefix\s+\$\(BUILD_ROOT\)/,\$\(C_SOURCES:\.c=\.o\)\)' `
    -Message 'C object paths do not preserve source hierarchy.'
Assert-FileContainsPattern -RelativePath 'Targets\SilverStar_F407\target.mk' `
    -Pattern 'PLATFORM_BACKEND\s*:=\s*STM32F4' `
    -Message 'SilverStar_F407 target does not select the STM32F4 backend explicitly.'
Assert-FileContainsPattern -RelativePath 'Targets\SilverStar_F407\target.mk' `
    -Pattern 'TARGET_MCU_FLAGS\s*:=\s*-mcpu=cortex-m4' `
    -Message 'SilverStar_F407 target does not own its MCU compiler flags.'
Assert-FileContainsPattern -RelativePath 'Targets\SilverStar_F407\target.mk' `
    -Pattern 'TARGET_LDSCRIPT\s*:=\s*STM32F407XX_FLASH\.ld' `
    -Message 'SilverStar_F407 target does not own its linker script selection.'
$eidePath = Join-Path $repoRoot '.eide\eide.yml'
$eideContent = Get-Content -Raw -LiteralPath $eidePath
$eideSourceDirs = @(Get-YamlListValues -Content $eideContent `
    -BlockPattern '(?ms)^srcDirs:\s*\r?\n(?<items>(?: {2}-[^\r\n]+\r?\n)+)' `
    -ItemPattern '^\s{2}-\s+(?<value>.+?)\s*$')
$eideVirtualSources = @(Get-YamlListValues -Content $eideContent `
    -BlockPattern '(?ms)^virtualFolder:\s*\r?\n.*?^ {2}files:\s*\r?\n(?<items>(?: {4}-\s+path:[^\r\n]+\r?\n)+)' `
    -ItemPattern '^\s{4}-\s+path:\s*(?<value>.+?)\s*$')
$eideIncludes = @(Get-YamlListValues -Content $eideContent `
    -BlockPattern '(?ms)^ {6}incList:\s*\r?\n(?<items>(?: {8}-[^\r\n]+\r?\n)+)' `
    -ItemPattern '^\s{8}-\s+(?<value>.+?)\s*$')
$eideDefines = @(Get-YamlListValues -Content $eideContent `
    -BlockPattern '(?ms)^ {6}defineList:\s*\r?\n(?<items>(?: {8}-[^\r\n]+\r?\n)+)' `
    -ItemPattern '^\s{8}-\s+(?<value>.+?)\s*$')
$eideExcludedSources = @(Get-YamlListValues -Content $eideContent `
    -BlockPattern '(?ms)^ {4}excludeList:\s*\r?\n(?<items>(?: {6}-[^\r\n]+\r?\n)+)' `
    -ItemPattern '^\s{6}-\s+(?<value>.+?)\s*$')
Assert-ArchitectureCondition -Condition ($eideSourceDirs.Count -ne 0) `
    -Message 'EIDE srcDirs is empty.'
$broadEideDirectories = @(
    'Algorithm', 'APP', 'Core', 'Devices', 'Drivers', 'Middlewares',
    'Platform', 'Protocol', 'System', 'ThirdParty'
)
$selectedBroadEideDirectories = @($eideSourceDirs | Where-Object {
    $broadEideDirectories -contains $_
})
Assert-ArchitectureCondition `
    -Condition ($selectedBroadEideDirectories.Count -eq 0) `
    -Message ('EIDE scans over-broad component roots: ' +
        ($selectedBroadEideDirectories -join ', '))
$missingEideDirectories = @($eideSourceDirs | Where-Object {
    -not (Test-Path -LiteralPath (Join-Path $repoRoot $_) -PathType Container)
})
Assert-ArchitectureCondition -Condition ($missingEideDirectories.Count -eq 0) `
    -Message ('EIDE source directories are missing: ' +
        ($missingEideDirectories -join ', '))
Assert-ArchitectureCondition `
    -Condition ($eideContent -match `
        '(?m)^outDir:\s*build\\EIDE\\SilverStar_F407\s*$') `
    -Message 'EIDE output is not isolated under build\EIDE\SilverStar_F407.'
Assert-ArchitectureCondition `
    -Condition ($eideContent -match '(?m)^\s+cpuType:\s*Cortex-M4\s*$') `
    -Message 'EIDE CPU is not Cortex-M4.'
Assert-ArchitectureCondition `
    -Condition ($eideContent -match `
        '(?m)^\s+floatingPointHardware:\s*single\s*$') `
    -Message 'EIDE FPU is not single precision.'
Assert-ArchitectureCondition `
    -Condition ($eideContent -match `
        '(?m)^\s+\$float-abi-type:\s*hard\s*$') `
    -Message 'EIDE float ABI is not hard.'
Assert-ArchitectureCondition `
    -Condition ($eideContent -match '(?m)^\s+language-c:\s*c11\s*$') `
    -Message 'EIDE C language mode is not C11.'
Assert-ArchitectureCondition `
    -Condition ($eideContent -match `
        '(?m)^\s+scatterFilePath:\s*STM32F407XX_FLASH\.ld\s*$') `
    -Message 'EIDE does not use the authoritative F407 linker script.'
Assert-ArchitectureCondition `
    -Condition ($eideContent -match `
        '(?m)^\s+C_FLAGS:\s*-include Targets/SilverStar_F407/Inc/platform_memory_target\.h -include Generated/Inc/project_flight_config\.h\s*$') `
    -Message 'EIDE does not force-include the target memory and flight configuration policies.'
Assert-ArchitectureCondition `
    -Condition ($eideContent -match '(?m)^\s+LIB_FLAGS:\s*-lc -lm -lnosys\s*$') `
    -Message 'EIDE target libraries do not match the authoritative F407 link.'
Assert-FileContainsPattern -RelativePath '.vscode\tasks.json' `
    -Pattern '"command"\s*:\s*"mingw32-make"' `
    -Message 'VS Code/EIDE workflow does not call the authoritative Make build.'
Assert-FileContainsPattern -RelativePath 'STM32F407XX_FLASH.ld' `
    -Pattern '_Min_Heap_Size\s*=\s*0x0\s*;' `
    -Message 'The target linker script still reserves a C runtime heap.'
Assert-FileContainsPattern -RelativePath 'Flight_Controller0.5.ioc' `
    -Pattern 'ProjectManager\.HeapSize=0x0' `
    -Message 'CubeMX project metadata does not preserve the zero-heap target.'
Assert-NoArchitecturePattern -Name `
    'CubeMX project metadata still owns FreeRTOS or a default task.' `
    -Paths @('Flight_Controller0.5.ioc') -Extensions @('.ioc') `
    -Pattern '(?i)FREERTOS|CMSIS_V2|defaultTask|rtos\.0\.ip'
Assert-FileContainsPattern -RelativePath 'Flight_Controller0.5.ioc' `
    -Pattern 'NVIC\.TimeBaseIP=TIM1' `
    -Message 'CubeMX no longer assigns the HAL tick to TIM1.'
Assert-FileContainsPattern -RelativePath 'Flight_Controller0.5.ioc' `
    -Pattern 'USART1\.BaudRate=230400' `
    -Message 'CubeMX IMU UART baudrate changed from 230400.'
Assert-FileContainsPattern -RelativePath 'Flight_Controller0.5.ioc' `
    -Pattern 'USART2\.BaudRate=921600' `
    -Message 'CubeMX GNSS UART baudrate changed from 921600.'
Assert-FileContainsPattern -RelativePath 'Flight_Controller0.5.ioc' `
    -Pattern 'USART3\.BaudRate=230400' `
    -Message 'CubeMX console UART baudrate changed from 230400.'
Assert-FileContainsPattern -RelativePath 'Flight_Controller0.5.ioc' `
    -Pattern 'Dma\.USART1_RX\.0\.Mode=DMA_CIRCULAR' `
    -Message 'CubeMX IMU RX DMA is no longer circular.'
Assert-FileContainsPattern -RelativePath 'Flight_Controller0.5.ioc' `
    -Pattern 'Dma\.USART2_RX\.2\.Mode=DMA_CIRCULAR' `
    -Message 'CubeMX GNSS RX DMA is no longer circular.'
Assert-FileContainsPattern -RelativePath 'Flight_Controller0.5.ioc' `
    -Pattern 'Dma\.USART3_RX\.4\.Mode=DMA_CIRCULAR' `
    -Message 'CubeMX console RX DMA is no longer circular.'

$iocContent = Get-Content -Raw -LiteralPath `
    (Join-Path $repoRoot 'Flight_Controller0.5.ioc')
$requiredIocEntries = @(
    @('Mcu.IPNb=11', 'CubeMX peripheral count does not reflect FreeRTOS removal.'),
    @('NVIC.PriorityGroup=NVIC_PRIORITYGROUP_4', 'CubeMX NVIC priority grouping changed.'),
    @('NVIC.SysTick_IRQn=true\:15\:0', 'CubeMX SysTick priority is not 15.'),
    @('NVIC.TIM1_UP_TIM10_IRQn=true\:15\:0', 'CubeMX TIM1 HAL tick priority is not 15.'),
    @('NVIC.USART1_IRQn=true\:5\:0', 'CubeMX USART1 IRQ priority is not 5.'),
    @('NVIC.USART2_IRQn=true\:5\:0', 'CubeMX USART2 IRQ priority is not 5.'),
    @('NVIC.USART3_IRQn=true\:5\:0', 'CubeMX USART3 IRQ priority is not 5.'),
    @('NVIC.EXTI9_5_IRQn=true\:5\:0', 'CubeMX EXTI9_5 IRQ priority is not 5.'),
    @('PA9.Signal=USART1_TX', 'CubeMX IMU UART TX mapping changed.'),
    @('PA10.Signal=USART1_RX', 'CubeMX IMU UART RX mapping changed.'),
    @('PD5.Signal=USART2_TX', 'CubeMX GNSS UART TX mapping changed.'),
    @('PD6.Signal=USART2_RX', 'CubeMX GNSS UART RX mapping changed.'),
    @('PB10.Signal=USART3_TX', 'CubeMX console UART TX mapping changed.'),
    @('PB11.Signal=USART3_RX', 'CubeMX console UART RX mapping changed.'),
    @('PA4.GPIO_Label=RADIO_NSS', 'CubeMX radio NSS mapping changed.'),
    @('PA5.Signal=SPI1_SCK', 'CubeMX radio SCK mapping changed.'),
    @('PA6.Signal=SPI1_MISO', 'CubeMX radio MISO mapping changed.'),
    @('PA7.Signal=SPI1_MOSI', 'CubeMX radio MOSI mapping changed.'),
    @('PB0.GPIO_Label=RADIO_RST', 'CubeMX radio reset mapping changed.'),
    @('PB1.GPIO_Label=RADIO_BUSY', 'CubeMX radio BUSY mapping changed.'),
    @('PE7.GPIO_Label=RADIO_DIO1', 'CubeMX radio DIO1 mapping changed.'),
    @('PE5.GPIO_Label=GNSS_RST', 'CubeMX GNSS reset mapping changed.'),
    @('PE6.GPIO_Label=GNSS_TIMEPULSE', 'CubeMX GNSS timepulse mapping changed.'),
    @('PB14.GPIO_Label=P_CONTROL2', 'CubeMX P_CONTROL2 mapping changed.'),
    @('PB15.GPIO_Label=P_CONTROL1', 'CubeMX P_CONTROL1 mapping changed.'),
    @('PC0.Signal=ADCx_IN10', 'CubeMX voltage ADC mapping changed.'),
    @('PD2.Signal=SDIO_CMD', 'CubeMX SDIO command mapping changed.'),
    @('PC12.Signal=SDIO_CK', 'CubeMX SDIO clock mapping changed.')
)
foreach ($iocEntry in $requiredIocEntries) {
    Assert-ArchitectureCondition -Condition $iocContent.Contains($iocEntry[0]) `
        -Message $iocEntry[1]
}

$makeOutput = @(& mingw32-make -s TARGET_PROFILE=SilverStar_F407 `
    CONFIG=Debug list-sources 2>&1)
$makeExitCode = $LASTEXITCODE
Assert-ArchitectureCondition -Condition ($makeExitCode -eq 0) `
    -Message ("Authoritative manifest evaluation failed:`n  " +
        ($makeOutput -join "`n  "))

if ($makeExitCode -eq 0) {
    $selectedSources = @($makeOutput | ForEach-Object { $_.ToString().Trim() } |
        Where-Object { $_ -match '\.c$' } |
        ForEach-Object { $_ -replace '\\', '/' })
    $uniqueSources = @($selectedSources | Sort-Object -Unique)
    Assert-ArchitectureCondition `
        -Condition ($selectedSources.Count -eq $uniqueSources.Count) `
        -Message 'The authoritative manifest selected duplicate C sources.'

    $missingSources = @($uniqueSources | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $repoRoot $_) -PathType Leaf)
    })
    Assert-ArchitectureCondition -Condition ($missingSources.Count -eq 0) `
        -Message ("Manifest references missing sources: " +
            ($missingSources -join ', '))

    $selectedKernelSources = @($uniqueSources | Where-Object {
        $_ -like 'ThirdParty/FreeRTOS-Kernel/*'
    } | Sort-Object)
    $expectedKernelSources = @(
        'ThirdParty/FreeRTOS-Kernel/list.c',
        'ThirdParty/FreeRTOS-Kernel/portable/GCC/ARM_CM4F/port.c',
        'ThirdParty/FreeRTOS-Kernel/queue.c',
        'ThirdParty/FreeRTOS-Kernel/tasks.c'
    ) | Sort-Object
    $kernelDifference = @(Compare-Object -ReferenceObject $expectedKernelSources `
        -DifferenceObject $selectedKernelSources)
    Assert-ArchitectureCondition -Condition ($kernelDifference.Count -eq 0) `
        -Message ("Unexpected FreeRTOS kernel source set: " +
            ($selectedKernelSources -join ', '))

    $forbiddenSelectedSources = @($uniqueSources | Where-Object {
        $_ -match ('(?i)(?:^|/)heap_[1-5]\.c$|cmsis_os2\.c$|' +
            '(?:^|/)(?:croutine|event_groups|stream_buffer|timers)\.c$|' +
            'port_stm32\.c$|provider\.c$')
    })
    Assert-ArchitectureCondition `
        -Condition ($forbiddenSelectedSources.Count -eq 0) `
        -Message ("Forbidden source entered the target build: " +
            ($forbiddenSelectedSources -join ', '))

    $wrongPlatformSources = @($uniqueSources | Where-Object {
        ($_ -like 'Platform/*') -and ($_ -notlike 'Platform/STM32F4/*')
    })
    Assert-ArchitectureCondition -Condition ($wrongPlatformSources.Count -eq 0) `
        -Message ("Unselected Platform backend entered the build: " +
            ($wrongPlatformSources -join ', '))

    $requiredStrategySources = @(
        'Algorithm/Calibration/Src/imu_six_face_calibration.c',
        'Algorithm/Alignment/Common/Src/attitude_alignment.c',
        'Algorithm/Alignment/Common/Src/attitude_preflight.c',
        'Algorithm/Alignment/GravityKnownYaw/Src/alignment_gravity_known_yaw.c',
        'Algorithm/Alignment/GravityKnownYaw/Src/alignment_strategy_binding.c',
        'Algorithm/INS/Coning2Sculling2/Src/ins_mechanization.c',
        'FlightLogic/Deployment/MultiTrigger/Src/flight_deployment.c',
        'FlightLogic/Landing/BarometerImuWindow/Src/flight_landing.c'
    )
    $selectedEstimatorTaskSources = @($uniqueSources | Where-Object {
        ($_ -eq 'APP/Src/estimator_task.c') -or
        ($_ -eq 'APP/Src/estimator_task_none.c')
    })
    Assert-ArchitectureCondition `
        -Condition ($selectedEstimatorTaskSources.Count -eq 1) `
        -Message ("Expected exactly one estimator task implementation: " +
            ($selectedEstimatorTaskSources -join ', '))
    if ($uniqueSources -contains 'APP/Src/estimator_task.c') {
        $requiredStrategySources += 'Algorithm/Estimator/KF6/Src/navigation_kf.c'
    }
    if ($uniqueSources -contains 'APP/Src/estimator_task_none.c') {
        $noneKfSources = @($uniqueSources | Where-Object {
            $_ -like 'Algorithm/Estimator/KF6/*'
        })
        Assert-ArchitectureCondition `
            -Condition ($noneKfSources.Count -eq 0) `
            -Message ("No-fusion estimator task still selects KF6 sources: " +
                ($noneKfSources -join ', '))
    }
    $missingStrategySources = @($requiredStrategySources | Where-Object {
        $uniqueSources -notcontains $_
    })
    Assert-ArchitectureCondition `
        -Condition ($missingStrategySources.Count -eq 0) `
        -Message ("Selected Strategy/Mode component sources are missing: " +
            ($missingStrategySources -join ', '))

    $unselectedStrategySources = @($uniqueSources | Where-Object {
        ($_ -like 'Algorithm/Alignment/GravityMagTriad/*') -or
        ($_ -like 'Algorithm/Alignment/HardwareQuat6AxisKnownYaw/*') -or
        ($_ -like 'Algorithm/Alignment/HardwareQuat9Axis/*')
    })
    Assert-ArchitectureCondition `
        -Condition ($unselectedStrategySources.Count -eq 0) `
        -Message ("Unselected Alignment Strategy entered the build: " +
            ($unselectedStrategySources -join ', '))
    $backupSources = @($uniqueSources | Where-Object {
        $_ -like 'backup/*'
    })
    Assert-ArchitectureCondition -Condition ($backupSources.Count -eq 0) `
        -Message ("Reference backup entered the build: " +
            ($backupSources -join ', '))

    # FCCG resolves strategies before rendering one immutable source graph.
    $fccgResolvedSourceGraph = Test-Path -LiteralPath (Join-Path $repoRoot 'Generated\project_sources.mk')
    if (-not $fccgResolvedSourceGraph) {
        $noneOutput = @(& mingw32-make -s TARGET_PROFILE=SilverStar_F407 `
            CONFIG=Debug ESTIMATOR_STRATEGY=None list-sources 2>&1)
        $noneExitCode = $LASTEXITCODE
        Assert-ArchitectureCondition -Condition ($noneExitCode -eq 0) `
            -Message ("Estimator=None manifest evaluation failed:`n  " +
                ($noneOutput -join "`n  "))
        if ($noneExitCode -eq 0) {
            $noneSources = @($noneOutput | ForEach-Object {
                $_.ToString().Trim() -replace '\\', '/'
            } | Where-Object { $_ -match '\.c$' })
            $noneKfSources = @($noneSources | Where-Object {
                $_ -like 'Algorithm/Estimator/KF6/*'
            })
            Assert-ArchitectureCondition -Condition ($noneKfSources.Count -eq 0) `
                -Message ("Estimator=None still selects KF6 sources: " +
                    ($noneKfSources -join ', '))
        }

    }

    $selectedAssemblySources = @($makeOutput | Where-Object {
        $_.ToString() -match '^Assembly:\s+'
    } | ForEach-Object {
        @(($_.ToString() -replace '^Assembly:\s+', '').Trim() -split '\s+')
    } | Where-Object { $_ -ne '' } | ForEach-Object {
        ConvertTo-ArchitecturePath -Path $_
    })
    $expectedEideSources = @($uniqueSources + $selectedAssemblySources |
        Sort-Object -Unique)

    $normalizedEideExcludes = @($eideExcludedSources | ForEach-Object {
        ConvertTo-ArchitecturePath -Path $_
    })
    $eideScannedSources = @()
    foreach ($sourceDirectory in $eideSourceDirs) {
        $absoluteSourceDirectory = Join-Path $repoRoot $sourceDirectory
        if (Test-Path -LiteralPath $absoluteSourceDirectory -PathType Container) {
            $directorySources = @(Get-ChildItem -LiteralPath `
                $absoluteSourceDirectory -Recurse -File | Where-Object {
                    @('.c', '.s', '.S') -contains $_.Extension
                } | ForEach-Object {
                    ConvertTo-ArchitecturePath -Path `
                        $_.FullName.Substring($repoRoot.Length + 1)
                } | Where-Object {
                    $normalizedEideExcludes -notcontains $_
                })
            $eideScannedSources += $directorySources
        }
    }
    $missingVirtualSources = @($eideVirtualSources | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $repoRoot $_) -PathType Leaf)
    })
    Assert-ArchitectureCondition -Condition ($missingVirtualSources.Count -eq 0) `
        -Message ('EIDE virtual source files are missing: ' +
            ($missingVirtualSources -join ', '))
    $normalizedVirtualSources = @($eideVirtualSources | ForEach-Object {
        ConvertTo-ArchitecturePath -Path $_
    })
    $rawEideSources = @($eideScannedSources + $normalizedVirtualSources)
    $selectedEideSources = @($rawEideSources | Sort-Object -Unique)
    Assert-ArchitectureCondition `
        -Condition ($rawEideSources.Count -eq $selectedEideSources.Count) `
        -Message 'EIDE selects duplicate C/assembly sources.'
    $eideSourceDifference = @(Compare-Object `
        -ReferenceObject $expectedEideSources `
        -DifferenceObject $selectedEideSources)
    $eideDifferenceSummary = @($eideSourceDifference | Select-Object -First 12 |
        ForEach-Object { '{0} [{1}]' -f $_.InputObject, $_.SideIndicator })
    Assert-ArchitectureCondition -Condition ($eideSourceDifference.Count -eq 0) `
        -Message ("EIDE C/assembly source graph differs from Make:`n  " +
            ($eideDifferenceSummary -join "`n  "))

    $configOutput = @(& mingw32-make -s TARGET_PROFILE=SilverStar_F407 `
        CONFIG=Debug list-build-config 2>&1)
    $configExitCode = $LASTEXITCODE
    Assert-ArchitectureCondition -Condition ($configExitCode -eq 0) `
        -Message ("Authoritative build configuration evaluation failed:`n  " +
            ($configOutput -join "`n  "))
    if ($configExitCode -eq 0) {
        $expectedIncludes = @($configOutput | Where-Object {
            $_.ToString() -match '^INCLUDE:'
        } | ForEach-Object {
            ConvertTo-ArchitecturePath -Path `
                ($_.ToString() -replace '^INCLUDE:', '').Trim()
        } | Sort-Object -Unique)
        $normalizedEideIncludes = @($eideIncludes | ForEach-Object {
            ConvertTo-ArchitecturePath -Path $_
        } | Sort-Object -Unique)
        $eideIncludeDifference = @(Compare-Object `
            -ReferenceObject $expectedIncludes `
            -DifferenceObject $normalizedEideIncludes)
        Assert-ArchitectureCondition `
            -Condition ($eideIncludeDifference.Count -eq 0) `
            -Message 'EIDE include directories differ from Make.'

        $expectedDefines = @($configOutput | Where-Object {
            $_.ToString() -match '^DEFINE:'
        } | ForEach-Object {
            ($_.ToString() -replace '^DEFINE:', '').Trim()
        } | Sort-Object -Unique)
        $normalizedEideDefines = @($eideDefines | Sort-Object -Unique)
        $eideDefineDifference = @(Compare-Object `
            -ReferenceObject $expectedDefines `
            -DifferenceObject $normalizedEideDefines)
        Assert-ArchitectureCondition `
            -Condition ($eideDefineDifference.Count -eq 0) `
            -Message 'EIDE preprocessor definitions differ from Make.'
    }
}

Assert-FileContainsPattern -RelativePath 'ThirdParty\FreeRTOS-Kernel\include\task.h' `
    -Pattern 'tskKERNEL_VERSION_NUMBER\s+"V11\.3\.0"' `
    -Message 'Vendored FreeRTOS kernel is not official V11.3.0.'
Assert-ArchitectureCondition `
    -Condition (Test-Path -LiteralPath `
        (Join-Path $repoRoot 'ThirdParty\FreeRTOS-Kernel\LICENSE.md') -PathType Leaf) `
    -Message 'Vendored FreeRTOS official LICENSE.md is missing.'
Assert-FileContainsPattern -RelativePath 'OS\FreeRTOS\FreeRTOSConfig.h' `
    -Pattern 'configSUPPORT_STATIC_ALLOCATION\s+1' `
    -Message 'FreeRTOS static allocation is not enabled.'
Assert-FileContainsPattern -RelativePath 'OS\FreeRTOS\FreeRTOSConfig.h' `
    -Pattern 'configSUPPORT_DYNAMIC_ALLOCATION\s+0' `
    -Message 'FreeRTOS dynamic allocation is not disabled.'
Assert-FileContainsPattern -RelativePath 'OS\FreeRTOS\FreeRTOSConfig.h' `
    -Pattern 'configMAX_PRIORITIES\s+8U' `
    -Message 'FreeRTOS priority count is not the reviewed 8-level model.'
Assert-FileContainsPattern -RelativePath 'OS\FreeRTOS\freertos_hooks.c' `
    -Pattern '\bvApplicationGetIdleTaskMemory\s*\(' `
    -Message 'Static Idle task storage hook is missing.'
Assert-FileContainsPattern -RelativePath 'Targets\SilverStar_F407\Src\freertos_target_irq.c' `
    -Pattern '\bxPortSysTickHandler\s*\(' `
    -Message 'STM32F407 SysTick is not routed to the native FreeRTOS port.'
Assert-FileContainsPattern -RelativePath 'Core\Src\stm32f4xx_hal_timebase_tim.c' `
    -Pattern '\bTIM1\b' `
    -Message 'HAL tick is no longer kept on TIM1.'
Assert-FileContainsPattern -RelativePath 'APP\Src\app_tasks.c' `
    -Pattern '\bxTaskCreateStatic\s*\(' `
    -Message 'APP tasks are not created through the static FreeRTOS API.'

Assert-FileContainsPattern -RelativePath 'System\User\system_user_config.h' `
    -Pattern 'SILVERSTAR_VERSION_PATCH\s+9' `
    -Message 'SilverStar firmware version is not 0.0.9.'
Assert-FileContainsPattern -RelativePath 'Protocol\Inc\air_protocol.h' `
    -Pattern 'AIR_PROFILE_COMPACT_V0\s*=\s*0U' `
    -Message 'AIR_PROFILE_COMPACT_V0 wire profile changed during refactoring.'
Assert-FileContainsPattern -RelativePath 'Protocol\SSLOG\schema\sslog_schema.json' `
    -Pattern '"format"\s*:\s*"SSLOG0"' `
    -Message 'SSLOG container version changed during refactoring.'
Assert-FileContainsPattern -RelativePath 'Protocol\SSLOG\schema\sslog_schema.json' `
    -Pattern '"endianness"\s*:\s*"little"' `
    -Message 'SSLOG schema does not explicitly retain little-endian wire order.'
Assert-FileContainsPattern `
    -RelativePath 'Protocol\SSLOG\Src\sslog_records.c' `
    -Pattern '\bSslogRecords_PayloadSerialize\s*\(' `
    -Message 'SSLOG protocol source is missing the payload serializer.'
Assert-FileContainsPattern `
    -RelativePath 'Protocol\SSLOG\Src\sslog_records.c' `
    -Pattern '\bSslogRecords_PayloadDeserialize\s*\(' `
    -Message 'SSLOG protocol source is missing the payload deserializer.'
Assert-FileContainsPattern `
    -RelativePath 'Protocol\SSLOG\Src\sslog_records.c' `
    -Pattern '\bSslogRecords_U64Get\s*\(' `
    -Message 'SSLOG decoder is not explicitly endian-aware.'
Assert-FileContainsPattern `
    -RelativePath 'Protocol\SSLOG\Src\sslog_records.c' `
    -Pattern '\bSslogRecords_U32Put\s*\(' `
    -Message 'SSLOG encoder is not explicitly endian-aware.'
Assert-FileContainsPattern `
    -RelativePath 'Generated\Src\project_log_config.c' `
    -Pattern 's_project_log_streams\s*\[' `
    -Message 'Project log-stream selection is not isolated in Generated glue.'
Assert-NoArchitecturePattern -Name `
    'SSLOG protocol directly copies or casts a C payload struct as wire bytes.' `
    -Paths @('Protocol\SSLOG') `
    -Pattern ('(?i)memcpy\s*\([^;\r\n]*(?:record->payload|record\.payload)|' +
        '\(\s*(?:const\s+)?FlightLog[A-Za-z0-9_]*\s*\*\s*\)\s*&?buffer')
foreach ($descriptor in @(
    'DEVICE_DESCRIPTOR', 'ALGORITHM_DESCRIPTOR', 'LOG_STREAM_DESCRIPTOR')) {
    Assert-FileContainsPattern `
        -RelativePath 'Protocol\SSLOG\schema\sslog_schema.json' `
        -Pattern ('"name"\s*:\s*"' + $descriptor + '"') `
        -Message "SSLOG schema is missing $descriptor."
}

$sslogSchemaPath = Join-Path $repoRoot `
    'Protocol\SSLOG\schema\sslog_schema.json'
$sslogHeaderPath = Join-Path $repoRoot `
    'Protocol\SSLOG\Inc\sslog_records.h'
try {
    $sslogSchema = Get-Content -Raw -LiteralPath $sslogSchemaPath |
        ConvertFrom-Json
    $sslogHeader = Get-Content -Raw -LiteralPath $sslogHeaderPath
    $sslogRecords = @($sslogSchema.records)
    Assert-ArchitectureCondition -Condition ($sslogRecords.Count -eq 28) `
        -Message 'SSLOG reference schema record count is not 28.'
    $sslogIds = @($sslogRecords | ForEach-Object { $_.id })
    Assert-ArchitectureCondition `
        -Condition (($sslogIds | Sort-Object -Unique).Count -eq
                    $sslogIds.Count) `
        -Message 'SSLOG reference schema contains duplicate Record IDs.'
    foreach ($sslogRecord in $sslogRecords) {
        $recordId = [Convert]::ToUInt32(
            $sslogRecord.id.ToString().Substring(2), 16)
        $recordIdText = '{0:X2}' -f $recordId
        $enumPattern = ('\b' + [regex]::Escape(
            $sslogRecord.enum.ToString()) + '\s*=\s*0x' +
            $recordIdText + 'U\b')
        Assert-ArchitectureCondition `
            -Condition ([regex]::IsMatch($sslogHeader, $enumPattern)) `
            -Message ("SSLOG schema/header Record ID mismatch for " +
                $sslogRecord.enum)
        $sizePattern = ('\b' + [regex]::Escape(
            $sslogRecord.size_macro.ToString()) + '\s+' +
            [regex]::Escape($sslogRecord.payload_size.ToString()) + 'U\b')
        Assert-ArchitectureCondition `
            -Condition ([regex]::IsMatch($sslogHeader, $sizePattern)) `
            -Message ("SSLOG schema/header payload size mismatch for " +
                $sslogRecord.enum)
    }
}
catch {
    Assert-ArchitectureCondition -Condition $false `
        -Message ("SSLOG schema/header validation failed: " +
            $_.Exception.Message)
}

if ($script:failures.Count -ne 0) {
    Write-Output ("SilverStar architecture check failed: checks={0} failures={1}" -f `
        $script:checkCount, $script:failures.Count)
    foreach ($failure in $script:failures) {
        Write-Output "FAIL: $failure"
    }
    exit 1
}

Write-Output ("SilverStar architecture check passed: checks={0} failures=0" -f `
    $script:checkCount)
Write-Output 'SSLOG codecs are ordinary endian-aware protocol source; Make requires no Python.'
Write-Output 'Authoritative target source graph and FreeRTOS source set are valid.'
