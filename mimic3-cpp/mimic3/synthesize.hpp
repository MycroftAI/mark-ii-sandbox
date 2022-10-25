#ifndef SYNTHESIZE_H_
#define SYNTHESIZE_H_

#include <filesystem>
#include <fstream>
#include <memory>
#include <iostream>
#include <vector>
#include <limits>
#include <chrono>

#include <onnxruntime_cxx_api.h>
#include <spdlog/spdlog.h>
#include <sndfile.h>

namespace mimic3 {
    const std::string instanceName{"mimic3"};
    const float MAX_WAV_VALUE = 32767.0f;

    struct mimic3_Session {
        Ort::Session onnx;
        std::vector<char*> inputNames;
        std::vector<char*> outputNames;
        Ort::AllocatorWithDefaultOptions allocator;
        Ort::SessionOptions options;

        mimic3_Session() : onnx(nullptr) {};
    };

    mimic3_Session createSession(std::filesystem::path modelPath) {
        mimic3_Session session;
        Ort::Env env(OrtLoggingLevel::ORT_LOGGING_LEVEL_WARNING, instanceName.c_str());
        env.DisableTelemetryEvents();

        // session.options.SetIntraOpNumThreads(1);
        // session.options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
        session.options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_DISABLE_ALL);
        session.options.DisableCpuMemArena();
        session.options.DisableMemPattern();
        session.options.DisableProfiling();

        spdlog::debug("Loading onnx model: {}", modelPath.string());
        session.onnx = Ort::Session(env, modelPath.c_str(), session.options);
        spdlog::info("Loaded onnx model");

        size_t numInputNodes = session.onnx.GetInputCount();
        size_t numOutputNodes = session.onnx.GetOutputCount();

        for (size_t i = 0; i < numInputNodes; i++) {
            session.inputNames.push_back(session.onnx.GetInputName(i, session.allocator));
        }

        for (size_t i = 0; i < numOutputNodes; i++) {
            session.outputNames.push_back(session.onnx.GetOutputName(i, session.allocator));
        }

        return session;
    }

    struct mimic3_Result {
        double inferSeconds;
        double audioSeconds;
        double realTimeFactor;
    };

    mimic3_Result synthesize(mimic3_Session& session,
                             std::filesystem::path outputPath,
                             std::vector<int64_t>* phonemeIds,
                             float noiseScale,
                             float lengthScale,
                             float noiseW,
                             int sampleRate) {
        mimic3_Result result;
        spdlog::debug("Allocating tensors");
        auto memoryInfo = Ort::MemoryInfo::CreateCpu(OrtAllocatorType::OrtArenaAllocator,
                                                     OrtMemType::OrtMemTypeDefault);

        std::vector<int64_t> phonemeIdLengths{(int64_t)phonemeIds->size()};
        std::vector<float> scales{noiseScale, lengthScale, noiseW};

        std::vector<Ort::Value> inputTensors;
        std::vector<int64_t> phonemeIdsShape{1, (int64_t)phonemeIds->size()};
        inputTensors.push_back(Ort::Value::CreateTensor<int64_t>(
                                   memoryInfo,
                                   phonemeIds->data(), phonemeIds->size(),
                                   phonemeIdsShape.data(), phonemeIdsShape.size()));

        std::vector<int64_t> phomemeIdLengthsShape{(int64_t)phonemeIdLengths.size()};
        inputTensors.push_back(Ort::Value::CreateTensor<int64_t>(
                                   memoryInfo,
                                   phonemeIdLengths.data(), phonemeIdLengths.size(),
                                   phomemeIdLengthsShape.data(), phomemeIdLengthsShape.size()));

        std::vector<int64_t> scalesShape{(int64_t)scales.size()};
        inputTensors.push_back(Ort::Value::CreateTensor<float>(
                                   memoryInfo,
                                   scales.data(), scales.size(),
                                   scalesShape.data(), scalesShape.size()));

        spdlog::debug("Running inference");
        auto startTime = std::chrono::steady_clock::now();
        auto outputTensors = session.onnx.Run(
            Ort::RunOptions{nullptr},
            session.inputNames.data(),
            inputTensors.data(),
            inputTensors.size(),
            session.outputNames.data(),
            session.outputNames.size());
        auto endTime = std::chrono::steady_clock::now();
        spdlog::debug("Inference complete");

        if ((outputTensors.size() != 1) || (!outputTensors.front().IsTensor())) {
            spdlog::critical("Invalid output tensors");
            throw std::runtime_error("Invalid output tensors");
        }
        auto inferDuration = std::chrono::duration<double>(endTime - startTime);
        result.inferSeconds = inferDuration.count();

        const float* audio = outputTensors.front().GetTensorData<float>();
        auto audioShape = outputTensors.front().GetTensorTypeAndShapeInfo().GetShape();
        int64_t audioCount = audioShape[audioShape.size() - 1];

        result.audioSeconds = (double)audioCount / (double)sampleRate;
        result.realTimeFactor = 0.0;
        if (result.audioSeconds > 0) {
            result.realTimeFactor = result.inferSeconds / result.audioSeconds;
        }

        // Write WAV
        spdlog::debug("Writing WAV file: {}", outputPath.string());
        float maxAudioValue = 0.01f;
        for (int64_t i = 0; i < audioCount; i++) {
            float audioValue = std::abs(audio[i]);
            if (audioValue > maxAudioValue) {
                maxAudioValue = audioValue;
            }
        }

        SF_INFO sfInfo;
        sfInfo.channels = 1;
        sfInfo.samplerate = sampleRate;
        sfInfo.format = SF_FORMAT_WAV | SF_FORMAT_PCM_16;

        SNDFILE* outputFile = sf_open(outputPath.c_str(), SFM_WRITE, &sfInfo);

        // Scale audio to fill range and convert to int16
        float audioScale = (MAX_WAV_VALUE / std::max(0.01f, maxAudioValue));
        for (int64_t i = 0; i < audioCount; i++) {
            int16_t intAudioValue = static_cast<int16_t>(
                std::clamp(audio[i] * audioScale,
                           static_cast<float>(std::numeric_limits<int16_t>::min()),
                           static_cast<float>(std::numeric_limits<int16_t>::max())));

            sf_write_short(outputFile, &intAudioValue, /*items*/ 1);
        }

        sf_close(outputFile);

        // Clean up
        spdlog::debug("Cleaning up");
        for (size_t i = 0; i < outputTensors.size(); i++) {
            Ort::OrtRelease(outputTensors[i].release());
        }

        for (size_t i = 0; i < inputTensors.size(); i++) {
            Ort::OrtRelease(inputTensors[i].release());
        }

        return result;
    }
}

#endif // SYNTHESIZE_H_
