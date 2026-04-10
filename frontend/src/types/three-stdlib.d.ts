declare module "three/examples/jsm/loaders/GLTFLoader.js" {
  import {
    Loader,
    LoadingManager,
    Group,
    LoaderUtils,
    Texture,
    Material,
    Mesh,
    SkinnedMesh,
    Camera,
    AnimationClip,
    Object3D,
  } from "three";

  export interface GLTF {
    scene: Group;
    scenes: Group[];
    animations: AnimationClip[];
    cameras: Camera[];
    asset: {
      copyright?: string;
      generator?: string;
      version?: string;
      minVersion?: string;
      extensions?: Record<string, unknown>;
      extras?: unknown;
    };
    parser: GLTFParser;
    userData: Record<string, unknown>;
  }

  export class GLTFParser {
    json: Record<string, unknown>;
    options: Record<string, unknown>;

    getDependency(type: string, index: number): Promise<unknown>;
    getDependencies(type: string): Promise<unknown[]>;
    assignTexture(
      materialParams: Record<string, unknown>,
      mapName: string,
      mapDef: Record<string, unknown>
    ): Promise<Texture | null>;
  }

  export class GLTFLoader extends Loader {
    dracoLoader: unknown;
    ktx2Loader: unknown;
    meshoptDecoder: unknown;

    constructor(manager?: LoadingManager);

    register(
      callback: (parser: GLTFParser) => unknown
    ): GLTFLoader;

    unregister(
      callback: (parser: GLTFParser) => unknown
    ): GLTFLoader;

    load(
      url: string,
      onLoad: (gltf: GLTF) => void,
      onProgress?: (event: ProgressEvent<EventTarget>) => void,
      onError?: (event: unknown) => void
    ): void;

    parse(
      data: ArrayBuffer | string,
      path: string,
      onLoad: (gltf: GLTF) => void,
      onError?: (event: unknown) => void
    ): void;

    setDRACOLoader(dracoLoader: unknown): GLTFLoader;
    setKTX2Loader(ktx2Loader: unknown): GLTFLoader;
    setMeshoptDecoder(meshoptDecoder: unknown): GLTFLoader;
  }
}