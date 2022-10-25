#include <algorithm>
#include <assert.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#include <json/json.h>
#include <spdlog/spdlog.h>
#include <spdlog/sinks/stdout_color_sinks.h>

#include "phonemize.hpp"
#include "synthesize.hpp"

using namespace std;

void printHelp() {
    std::cout << "mimic3 <model> [output_dir]" << std::endl;
}

int main(int argc, char *argv[]) {
    // Log to stderr instead of stdout
    spdlog::set_default_logger(spdlog::stderr_color_st("mimic3"));
    spdlog::set_level(spdlog::level::debug);

    if (argc < 2) {
        printHelp();
        return EXIT_SUCCESS;
    }

    std::filesystem::path modelPath(argv[1]);
    std::optional<std::filesystem::path> outputDirectory;

    if (argc > 2) {
        // Output directory for WAV files
        outputDirectory = std::filesystem::path(argv[2]);
        spdlog::debug("Creating output directory: {}", outputDirectory.value().string());
        std::filesystem::create_directories(outputDirectory.value());
    }

    // Verify model file exists
    std::ifstream modelFile(modelPath.c_str(), ios::binary);
    if (!modelFile.good()) {
        spdlog::critical("Model not set correctly or doesn't exist: {}", modelPath.string());
        return EXIT_FAILURE;
    }

    // Load phoneme map
    std::optional<mimic3::PhonemeIdMap> idMap;
    std::filesystem::path idMapPath = modelPath.parent_path() / "phoneme_id_map.json";
    std::ifstream idMapFile(idMapPath.c_str());
    if (idMapFile.good()) {
        spdlog::debug("Loading phoneme id map: {}", idMapPath.string());
        idMap.emplace();
        mimic3::loadPhonemeIdMap(idMapFile, &idMap.value());
        spdlog::info("Loaded phoneme id map");
    } else {
        spdlog::warn("Missing phoneme id map: {}", idMapPath.string());
    }


    // Initialize
    mimic3::initializeEspeak();
    auto session = mimic3::createSession(modelPath);

    // -----------

    // Read lines of JSON from standard input.
    // Format:
    // { "text": "Text to synthesize", "mimic3": { "output_path": "/optional/path/to/file.wav" } }
    //
    std::size_t lineIndex = 0;
    std::string line;
    while (getline(std::cin, line)) {
        std::stringstream lineStream(line);
        mimic3::mimic3_Request request;
        mimic3::parseRequest(lineStream, request);
        mimic3::phonemize(request);
        mimic3::phonemes2ids(request, idMap);

        if (!request.outputPath) {
            // Path to output WAV file
            std::stringstream outputName;
            outputName << lineIndex << ".wav";

            if (outputDirectory.has_value()) {
                // Relative to output directory
                request.outputPath = outputDirectory;
                request.outputPath.value().append(outputName.str());
            } else {
                // Relative to current directory
                request.outputPath = std::filesystem::path(outputName.str());
            }
        }

        if (!request.outputPath) {
            throw std::runtime_error("No output path for audio");
        }

        auto phonemeIds = &request.phonemeIds.value();
        if (phonemeIds->empty()) {
            throw std::runtime_error("Empty phoneme ids");
        }

        spdlog::debug("Synthesizing audio with {} phoneme id(s)", phonemeIds->size());
        auto result = synthesize(
            session,
            request.outputPath.value(),
            phonemeIds,
            request.noiseScale,
            request.lengthScale,
            request.noiseW,
            /*sampleRate*/ 22050);

        spdlog::info("Real-time factor: {} (infer={}, audio={})",
                     result.realTimeFactor,
                     result.inferSeconds,
                     result.audioSeconds);

        spdlog::info("Wrote {}", request.outputPath.value().string());
        lineIndex++;

        std::cout << line << std::endl;
    }

    mimic3::terminateEspeak();
    spdlog::info("Exiting");

    return EXIT_SUCCESS;
}
