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


std::mutex mtx_cout; //mutex protecting global variable cout

void printmutex(std::ostream& os, std::string name, std::string msg){
  std::unique_lock<std::mutex> unique_cout(mtx_cout);
  os << "[" << name << "]: "<< msg << std::endl;
}

class orchestrator;

class worker{
private:
  std::thread* th;
public:
  //orchestrator* orch;
  std::string name;
  std::mutex mtx_worker; //mutex protecting global variable a
  std::condition_variable cond_worker;
  std::deque<std::string> pending_tasks;
  int a;
  bool terminate, worker_turn;
  //worker(orchestrator* _orch, std::string _name) : orch(_orch), name(_name){
  worker(std::string _name) : name(_name){
    a = 0; terminate = false; worker_turn = false;
    th = new std::thread(&worker::work, this);
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
  //this simulates work and dotask
  void work() {
    while (!terminate) {//attribute terminate is controlled by orchestrator
      //printmutex(std::cout, name, "Need to continue working...");
      std::unique_lock<std::mutex> unique_worker(mtx_worker);//std::unique_lock with this constructor also invokes lock
      cond_worker.wait(unique_worker, [this] { return this->worker_turn; });
      if (!terminate) {
	//critical section
	dotask();
	//critical section end
      }
      //when working normally or when terminating:
      worker_turn = false;
      // manual unlocking is done before notifying, to avoid waking up
      // the waiting thread only to block again (see notify_one for details)
      unique_worker.unlock();
      cond_worker.notify_one();
    }
    printmutex(std::cout, name, "Work finished");
    
  }//std::unique_lock invokes unlock when exiting the scope, in this case the function

  //this method can be virtual and subclasses reimplement it accordingly
  void dotask(){
    a++;
  }
};

class orchestrator{
public:
  std::string llm_response;
  std::map<std::string, worker*>* allworkers;
  //real_clock

  orchestrator(std::map<std::string, worker*>* _allworkers, int workcycles) : allworkers(_allworkers){
    
    //others

    //main loop
    assign_tasks(workcycles);
  }
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
  void assign_tasks(int k){
    const unsigned int mod = 0;
    while (k >= 0){//simulating a fixed ammount of tasks
      for (auto it = allworkers->begin(); it != allworkers->end(); ++it){
	std::mutex* mtx_worker = &it->second->mtx_worker;
	std::condition_variable* cv = &it->second->cond_worker;
	bool* worker_turn = &it->second->worker_turn; 
	std::unique_lock<std::mutex> unique_worker(*mtx_worker);//std::unique_lock with this constructor also invokes lock
	cv->wait(unique_worker, [worker_turn] { return *worker_turn == false; });
	if (k == 0){//just after all iterations we flag the worker that next turn is to terminate
	  it->second->terminate = true;
	}
       
	//TODO:prepare pending_tasks of worker
	  
	//pass turn to worker EVEN WHEN TERMINATING
	*worker_turn = true;
	unique_worker.unlock();
	cv->notify_one(); //notify worker that it can work now
      }
      k--;
    }
  }

  void respond(){

  }

  void setllm_response(std::string _llm_response){ llm_response = _llm_response;  }
  
};


int main(){
  std::cout << "Hello CMake." << std::endl;
  int workcycles = 10000;
  std::map<std::string, worker*>* allworkers = new std::map<std::string, worker*>();
  worker* wk = new worker("speech");
  const auto [it_speech, success] = allworkers->insert({"speech", wk});
  //if (!success)
  wk = new worker("speech2");
  const auto [it_speech2, success2] = allworkers->insert({"speech2", wk});
  //if (!success)
  wk = new worker("speech3");
  const auto [it_speech3, success3] = allworkers->insert({"speech3", wk});
  //if (!success)
  wk = new worker("speech4");
  const auto [it_speech4, success4] = allworkers->insert({"speech4", wk});
  //if (!success)
  
  orchestrator* orch = new orchestrator(allworkers, workcycles);
  delete orch;
  
  return 0;
}
