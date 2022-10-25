#ifndef PHONEMIZE_H_
#define PHONEMIZE_H_

#include <filesystem>
#include <iostream>
#include <map>
#include <string_view>
#include <set>
#include <vector>

#include <espeak-ng/speak_lib.h>
#include <json/json.h>
#include <spdlog/spdlog.h>
#include <utf8.h>

namespace mimic3 {
  const std::string DEFAULT_VOICE{"en-us"};

  // Meta symbols (phoneme ids) used for mimic3
  const int64_t PAD = 0;  // padding (interspersed)
  const int64_t BOS = 1;  // beginning of sentence
  const int64_t EOS = 2;  // end of sentence

  // Characters that are assumed to cause eSpeak-ng to break apart a sentence
  // into clauses.
  const std::set<char32_t> CLAUSE_BREAKERS{ U'.', U'?', U'!', U',', U';', U':' };

  typedef std::map<char32_t, std::vector<int64_t>> PhonemeIdMap;

  void loadPhonemeIdMap(std::istream& inputStream,
                        PhonemeIdMap* idMap) {
    Json::Value root;
    Json::CharReaderBuilder builder;
    JSONCPP_STRING errs;
    if (!parseFromStream(builder, inputStream, &root, &errs)) {
      spdlog::critical("Failed to load phoneme id map: {}", errs);
      throw std::runtime_error("Failed to load phoneme id map");
    }

    // phoneme -> [id]
    for (std::string phoneme : root.getMemberNames()) {
      auto num_chars = utf8::distance(phoneme.begin(), phoneme.end());
      if (num_chars > 1) {
        spdlog::critical("Phonemes cannot be more than one codepoint in length: {}", phoneme);
        throw std::runtime_error("Failed to load phoneme id map");
      }

      utf8::iterator character_iter(phoneme.begin(), phoneme.begin(), phoneme.end());
      auto codepoint = *character_iter;
      for (auto id : root[phoneme]) {
        (*idMap)[codepoint].push_back(id.asInt64());
      }
    }
  }

  void initializeEspeak() {
    spdlog::debug("Initializing eSpeak-ng");
    int result = espeak_Initialize(AUDIO_OUTPUT_SYNCHRONOUS,
                                   /*buflength*/ 0,
                                   /*path*/ NULL,
                                   /*options*/ 0);
    if (result < 0) {
      spdlog::critical("Failed to initialize eSpeak-ng");
      throw std::runtime_error("Failed to initialize eSpeak-ng");
    }
  }

  void terminateEspeak() {
    spdlog::debug("Terminating eSpeak-ng");
    espeak_Terminate();
  }

  struct mimic3_Request {
    std::string text;
    std::string voice;
    std::optional<std::vector<char32_t>> phonemes;
    std::optional<std::vector<int64_t>> phonemeIds;
    std::optional<std::filesystem::path> outputPath;
    float noiseScale = 0.667f;
    float lengthScale = 1.0f;
    float noiseW = 0.8f;

    mimic3_Request() : voice(DEFAULT_VOICE) {};
  };

  void parseRequest(std::istream& inputStream, mimic3_Request& request) {
    // Parses JSON request
    // {
    //   "text": "Text to synthesize",
    //   "phonemes": [...],       (optional list of strings)
    //   "phoneme_ids": [...],    (optional list of integers)
    //   "output_path": "...",    (optional WAV path)
    //   "espeak": {
    //      "voice": "en-us"      (override voice)
    //    },
    //   "mimic3": {
    //      "noise_scale": 0.667,
    //      "length_scale": 1.0,
    //      "noise_w": 0.8,
    //    },
    // }
    Json::Value root;
    Json::CharReaderBuilder builder;
    JSONCPP_STRING errs;
    if (!parseFromStream(builder, inputStream, &root, &errs)) {
      spdlog::critical("Failed to parse request: {}", errs);
      throw std::runtime_error("Failed to parse request");
    }

    // Text to synthesize
    request.text = root.get("text", "").asString();

    if (root.isMember("output_path")) {
      request.outputPath = std::filesystem::path(root["output_path"].asString());
    }

    if (root.isMember("phonemes")) {
      // TODO
    }

    if (root.isMember("phoneme_ids")) {
      auto phonemeIdsValue = root["phoneme_ids"];
      auto numIds = (size_t)phonemeIdsValue.size();

      // Copy into request
      request.phonemeIds.emplace(numIds);
      auto phonemeIds = &request.phonemeIds.value();
      size_t idIndex = 0;
      for (auto const& idValue : phonemeIdsValue) {
        (*phonemeIds)[idIndex] = idValue.asInt64();
        idIndex++;
      }

      spdlog::debug("Copied {} phoneme id(s) from request", phonemeIds->size());
    }

    // voice
    if (root.isMember("espeak")) {
      auto espeakValue = root["espeak"];
      if (espeakValue.isMember("voice")) {
        // Override default voice
        request.voice = espeakValue["voice"].asString();
      }
    }

    // outputPath, etc.
    if (root.isMember("mimic3")) {
      auto mimic3Value = root["mimic3"];
      if (mimic3Value.isMember("noise_scale")) {
        request.noiseScale = mimic3Value["noise_scale"].asFloat();
      }

      if (mimic3Value.isMember("length_scale")) {
        request.lengthScale = mimic3Value["length_scale"].asFloat();
      }

      if (mimic3Value.isMember("noise_w")) {
        request.noiseW = mimic3Value["noise_w"].asFloat();
      }

      // TODO: speaker
      //
      // TODO: SSML
    }

  }  /* parseRequest */

  void phonemize(mimic3_Request& request) {
    if (request.phonemes || request.phonemeIds) {
      spdlog::debug("Request phonemes or ids are already present");
      return;
    }

    request.phonemes.emplace();
    auto phonemes = &request.phonemes.value();

    spdlog::debug("Setting eSpeak-ng voice: {}", request.voice);
    int result = espeak_SetVoiceByName(request.voice.c_str());
    if (result != 0) {
      spdlog::critical("Failed to set eSpeak-ng voice: {}", request.voice);
      throw std::runtime_error("Failed to set eSpeak-ng voice");
    }

    std::string text(request.text);
    std::vector<char32_t> textClauseBreakers;

    utf8::iterator textIter(text.begin(), text.begin(), text.end());
    utf8::iterator textIterEnd(text.end(), text.begin(), text.end());

    while (textIter != textIterEnd) {
      auto codepoint = *textIter;
      if (CLAUSE_BREAKERS.contains(codepoint)) {
        textClauseBreakers.push_back(codepoint);
      }

      textIter++;
    }

    const char* inputTextPointer = text.c_str();
    size_t clauseBreakerIndex = 0;

    spdlog::debug("Phonemizing text: {}", request.text);
    while (inputTextPointer != NULL) {
      std::string clausePhonemes(
        espeak_TextToPhonemes((const void**)&inputTextPointer,
                              /*textmode*/ espeakCHARS_AUTO,
                              /*phonememode = IPA*/ 0x02));

      spdlog::debug("Phonemes: {}", clausePhonemes);

      utf8::iterator phonemeIter(clausePhonemes.begin(),
                                 clausePhonemes.begin(),
                                 clausePhonemes.end());
      utf8::iterator phonemeEnd(clausePhonemes.end(),
                                clausePhonemes.begin(),
                                clausePhonemes.end());

      phonemes->insert(phonemes->end(), phonemeIter, phonemeEnd);
      if (clauseBreakerIndex < textClauseBreakers.size()) {
        phonemes->push_back(textClauseBreakers[clauseBreakerIndex]);
        clauseBreakerIndex++;
      }
    }

  }  /* phonemize */

  void phonemes2ids(mimic3_Request& request, std::optional<PhonemeIdMap>& maybeIdMap) {
    if (request.phonemeIds.has_value()) {
      spdlog::debug("Phoneme ids are already present");
      return;
    }

    if (!request.phonemes) {
      throw std::runtime_error("No phonemes for request");
    }

    if (!maybeIdMap) {
      throw std::runtime_error("No phoneme id map");
    }

    auto idMap = &maybeIdMap.value();
    auto phonemes = &request.phonemes.value();
    spdlog::debug("Mapping {} phoneme(s) to ids", phonemes->size());

    request.phonemeIds.emplace();
    auto phonemeIds = &request.phonemeIds.value();

    phonemeIds->push_back(BOS);
    phonemeIds->push_back(PAD);

    for (auto phoneme = phonemes->begin(); phoneme != phonemes->end(); phoneme++) {
      if (idMap->contains(*phoneme)) {
        for (auto id : (*idMap)[*phoneme]) {
          phonemeIds->push_back(id);
          phonemeIds->push_back(PAD);
        }
      }
    }

    phonemeIds->push_back(EOS);

  }  /* phonemes2ids */

}


#endif // PHONEMIZE_H_
