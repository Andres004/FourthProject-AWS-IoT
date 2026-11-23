#pragma once

#include "ShadowTransport.h"
#include "config_common.h"

/**
 * @brief Replaces AWS with the Serial Monitor in the local_test environment.
 *
 * Each input line is processed as an /update/delta document, for example
 * {"state":{"window":"open"}}. Reports are printed instead of published.
 */
class SerialShadowClient : public ShadowTransport {
 public:
  void begin() override;
  void update(uint32_t nowMs) override;
  bool isConnected() const override;
  bool publishReported(const char* payload) override;

 private:
  char line_[config::local_test::MAX_LINE_LENGTH];
  size_t lineLength_ = 0;
};
