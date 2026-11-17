#include <iostream>
#include <syncstream>
#include <chrono>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <map>
#include <deque>
#include <string>
//#include "lib/lib.h"


#define ORCH_WINDOW 1000000 //1s



void printmutex(std::ostream& os, std::string name, std::string msg);

class Msg {
public:
  int src;
  int dst;
  int value;
  std::string msg;
  Msg(): src(0), dst(0), value(0), msg(""){};
  Msg(int _src, int _dst, int _value, std::string message) : src(_src), dst(_dst), value(_value), msg(message){}
};

std::ostream& operator<<(std::ostream &os, const Msg &m);

class Params {
public:
  int k;
  bool keepwork;
  //bool blocking;
  Msg* m;
  //Params(int _k, bool _blocking, Msg* _m) : k(_k), keepwork(true), blocking(_blocking), m(_m) {}
  Params(int _k, Msg* _m) : k(_k), keepwork(true), m(_m) {}
};

std::ostream& operator<<(std::ostream& os, const Params& p);

class neck;
class NeckParams : public Params {
public:
  //Params need to be a pointer since thread constructor needs arguments to have move semantics, and the thread inside Params does not have!!!
  neck* other;
  //NeckParams(int _k, bool _blocking, Msg* _m, neck* _other) : Params(_k, _blocking, _m){
  NeckParams(int _k, Msg* _m, neck* _other) : Params(_k, _m){
    other = _other;
  }
};

std::ostream& operator<<(std::ostream& os, const NeckParams& p);

class orchestrator;

class worker{
protected:
  std::thread* th;
  inline Msg* popMsg(){
    std::unique_lock<std::mutex> unique_worker(mtx_worker);//std::unique_lock with this constructor also invokes lock
    cond_worker.wait(unique_worker, [this] { return this->worker_turn && !pending_tasks.empty(); });

    Msg* m = pending_tasks.front();//blocking because of condition variable
    pending_tasks.pop_front();

    unique_worker.unlock();
    cond_worker.notify_one();
    return m;
  }

public:
  //orchestrator* orch;
  int worker_id;
  std::string name;
  std::mutex mtx_worker; //mutex protecting global variable a
  std::condition_variable cond_worker;
  std::deque<Msg*> pending_tasks;
  int a;
  bool terminate, worker_turn;//terminate controls the main loop of the thread, once set to false in the next iteration the loop in work will exit and 
  //worker(orchestrator* _orch, std::string _name) : orch(_orch), name(_name){
  worker(int _worker_id, std::string _name) : worker_id(_worker_id),name(_name){
    a = 0; terminate = false; worker_turn = false;
    th = new std::thread();
  }

  bool operator==(const worker& other) const{
    return this->name == other.name;
  }

  bool operator<(const worker& other) const{
    return this->name < other.name;
  }
  //we do not implement copy or assignment constructor, we explicitly want them DISABLED, we don't want to copy threads!
  ~worker(){
    th->join();
    printmutex(std::cout, name, std::format("Valor de a: {}", a));
  }
  
  inline void pushMsg(Msg* m){
    std::unique_lock<std::mutex> unique_worker(mtx_worker);//std::unique_lock with this constructor also invokes lock

    pending_tasks.push_back(m);

    unique_worker.unlock();
  }

  //this simulates work and dotask
  void work(Params* p); 
  //this method can be virtual and subclasses reimplement it accordingly
  //once the derived classes have this implemented, remove!
  virtual void criticalSection();
  virtual void run(Params* p) = 0;
  virtual void setup(Params* p) = 0;
  virtual void criticalSection(Params* p) = 0;
  virtual void wrapUp(Params* p) = 0;
  
};

class neck : public worker{
public:
  //'this' must be of derived complete (non-virtual) class
  using worker::worker;//use parent constructor
  /*destructor must join threads,
    BEWARE when calling derived class destructor,
    first the derived class dtor is called, and then the base class
    therefore overriding virtual functions will be lost at exit of derived class dtor!!
    and the only things available are those of the base class
    that is why we need to reimplement the joins in the derived class
  */
  //should be called by orchestrator AFTER turning terminate to true
  ~neck() {
    //ESP_LOGI(pcTaskGetName(nullptr), "[%d]neck.dtor()", wrapth.thid);
    if(th->joinable())
      th->join();
  }

  virtual void run(Params* p) override {
    //ESP_LOGI(pcTaskGetName(nullptr), "[%d]neck.run()", wrapth.thid);
    th = new std::thread(&worker::work, this, p);
  }
  virtual void setup(Params* p) override;
  virtual void criticalSection(Params* p) override;
  virtual void wrapUp(Params* p) override;
  
};

class eyes : public worker{
public:
  //'this' must be of derived complete (non-virtual) class
  using worker::worker;//use parent constructor
  /*destructor must join threads,
    BEWARE when calling derived class destructor,
    first the derived class dtor is called, and then the base class
    therefore overriding virtual functions will be lost at exit of derived class dtor!!
    and the only things available are those of the base class
    that is why we need to reimplement the joins in the derived class
  */
  //should be called by orchestrator AFTER turning terminate to true
  ~eyes() {
    //ESP_LOGI(pcTaskGetName(nullptr), "[%d]neck.dtor()", wrapth.thid);
    if(th->joinable())
      th->join();
  }

  virtual void run(Params* p) override {
    //ESP_LOGI(pcTaskGetName(nullptr), "[%d]neck.run()", wrapth.thid);
    th = new std::thread(&worker::work, this, p);
  }
  virtual void setup(Params* p) override;
  virtual void criticalSection(Params* p) override;
  virtual void wrapUp(Params* p) override;
  
};

class orchestrator{
public:
  int orch_id;
  int workcycles;
  std::string llm_response;
  std::map<std::string, worker*>* allworkers;
  //real_clock
  //synchronous schedule(partitura) as a queue/list of actions-gestures for neck or eyes to play
  //for now is a synthetic live-generated messaages in assign_tasks
  
  orchestrator(int _orch_id, std::map<std::string, worker*>* _allworkers, int _workcycles) : orch_id(_orch_id), allworkers(_allworkers), workcycles(_workcycles){}
  orchestrator(orchestrator& other) : llm_response(other.llm_response) {
    delete allworkers;
    allworkers = new std::map<std::string, worker*>(*other.allworkers);
  }
  orchestrator operator=(orchestrator& other) {
    if (this != &other){
      llm_response = other.llm_response;
      delete allworkers;
      allworkers = other.allworkers;
    }
    return *this;
  }
  ~orchestrator(){
    for (auto it = allworkers->begin(); it != allworkers->end(); ++it){
      delete it->second;
      /*std::unique_lock<std::mutex> unique_cout(mtx_cout);
	std::cout << "[" << it->second->workerobj->name << "]:Valor de a: " << it->second->workerobj->a << std::endl;*/
    }
    delete allworkers;
  }

  //main loop
  //let's use mod == 0 always for the orchestrator and mod == 1 for workers
  void assign_tasks(int k);

  //void respond();
  //void setllm_response(std::string _llm_response);
  
};
