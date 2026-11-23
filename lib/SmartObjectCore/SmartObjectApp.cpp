/**
 * @file SmartObjectApp.cpp
 * @brief Setup and loop sequence shared by both SmartLoft boards.
 */
#include "SmartObjectApp.h"

#include "EventLog.h"
#include "config_common.h"

SmartObjectApp::SmartObjectApp(const Settings& settings,
                               DeviceComponent* const* components,
                               size_t componentCount)
    : components_(components),
      componentCount_(componentCount),
      wifi_(settings.wifiSsid, settings.wifiPassword),
#ifdef LOCAL_TEST_MODE
      shadow_(),
#else
      shadow_(wifi_, settings.shadow),
#endif
      reporter_(shadow_, components, componentCount) {
}

void SmartObjectApp::begin() {
  EventLog::begin();
  EventLog::record("BOOT");
  health_.begin();
  EventLog::recordf("LINK_CODE", "%lu",
                    static_cast<unsigned long>(config::device::LINK_CODE));

  statusLed_.begin();
  for (size_t i = 0; i < componentCount_; ++i) {
    components_[i]->begin();
  }

  shadow_.setHandlers(
      [this](JsonObjectConst desired, DesiredSource source) {
        applyDesired(desired, source);
      },
      // After every (re)connection the full state is reported again.
      [this] { reporter_.requestReport(); });
  wifi_.begin();
  shadow_.begin();
}

void SmartObjectApp::update(uint32_t nowMs) {
  health_.update(nowMs, wifi_.disconnections(), shadow_.disconnections());
  wifi_.update(nowMs);
  timeSync_.update(wifi_.isConnected());
  shadow_.update(nowMs);
  for (size_t i = 0; i < componentCount_; ++i) {
    components_[i]->update(nowMs);
  }
  reporter_.update(nowMs);
  statusLed_.update(nowMs, wifi_.isConnected(), shadow_.isConnected());
}

void SmartObjectApp::applyDesired(JsonObjectConst desired,
                                  DesiredSource source) {
  for (size_t i = 0; i < componentCount_; ++i) {
    components_[i]->applyDesired(desired, source);
  }
}
