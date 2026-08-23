BUILD_MANIFESTS += Board/SilverStar_0_5/module.mk

C_SOURCES += \
  Board/SilverStar_0_5/Services/Src/indicator_service.c \
  Board/SilverStar_0_5/Services/Src/log_sink_service.c \
  Board/SilverStar_0_5/Services/Src/mission_action_service.c \
  Board/SilverStar_0_5/Services/Src/output_service.c \
  Board/SilverStar_0_5/Services/Src/power_service.c \
  Board/SilverStar_0_5/Services/Src/storage_service.c

C_INCLUDES += Board/SilverStar_0_5/Services/Inc
